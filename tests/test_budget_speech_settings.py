"""Spend gates and the ledger, SSML and clip handling, and settings parsing. No network."""

import asyncio
import dataclasses
from pathlib import Path
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx
import pytest

from agents.models import VoiceDirection
from agents.speech import SpeechClient, SpeechError, build_ssml, clip_hash, duration_of, looks_like_mp3
from app.budget import Budget, BudgetExceeded
from app.settings import Settings, load_settings

LIVE = Settings(openai_endpoint="https://x.services.ai.azure.com/openai/v1/responses", openai_api_key="k", openai_deployment="gpt-4.1-mini",
                llm_price_in=0.4, llm_price_out=1.6, live_cap_usd=1.0, speech_key="k", speech_region="eastus",
                voices={"en_casual": "v"})
NOON = lambda: datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)  # noqa: E731


def budget(tmp_path, settings=LIVE, **kw):
    return Budget(settings, tmp_path / "ledger.jsonl", now=NOON, **kw)


# --- budget ---------------------------------------------------------------------------------------------
def test_cost_is_tokens_times_price(tmp_path):
    b = budget(tmp_path)
    assert b.record_llm("k", 1_000_000, 0) == pytest.approx(0.4) and b.record_llm("k", 0, 1_000_000) == pytest.approx(1.6)
    assert b.record_speech("k", 1_000_000) == pytest.approx(22.0)
    t = b.totals()
    assert t.usd == pytest.approx(24.0) and t.calls == 3 and t.tokens_in == 1_000_000 and t.chars == 1_000_000


def test_ledger_survives_a_restart_and_the_cap_is_all_time(tmp_path):
    budget(tmp_path).record_llm("k", 2_000_000, 500_000)  # $1.60 > $1 cap
    tomorrow = Budget(LIVE, tmp_path / "ledger.jsonl", now=lambda: datetime(2026, 10, 28, 0, 1, tzinfo=timezone.utc))
    assert tomorrow.totals().calls == 1 and tomorrow.totals(today_only=True).calls == 0
    with pytest.raises(BudgetExceeded):  # a new day does not reset it: chunks are cached for good, so spend has a ceiling
        tomorrow.check_llm()


def test_live_cap_stops_live_generation_and_counts_model_and_voice(tmp_path):
    b = budget(tmp_path)
    b.check_llm()  # fine: nothing spent
    b.record_llm("k", 1_000_000, 0)  # $0.40
    b.check_llm()
    b.record_speech("k", 30_000)  # $0.66, so $1.06 in all
    with pytest.raises(BudgetExceeded):
        b.check_llm()


def test_cached_totals_match_a_fresh_read_of_the_ledger(tmp_path):
    b = budget(tmp_path)
    b.totals()  # loads the (empty) ledger, then keeps totals in memory
    b.record_llm("k", 1234, 56)
    b.record_speech("k", 789)
    fresh = budget(tmp_path).totals()
    assert b.totals() == fresh and fresh.calls == 2


@pytest.mark.parametrize("change", [{"live_cap_usd": 0.0}, {"llm_price_in": 0.0}, {"llm_price_out": 0.0}, {"openai_api_key": ""}])
def test_live_generation_is_off_when_cap_is_zero_or_a_price_is_missing(tmp_path, change):
    with pytest.raises(BudgetExceeded):
        budget(tmp_path, dataclasses.replace(LIVE, **change)).check_llm()


def test_run_limit_refuses_the_next_call_even_when_the_live_cap_is_ignored(tmp_path):
    b = budget(tmp_path, enforce_cap=False, run_max_usd=0.001)
    b.check_llm()
    b.record_llm("k", 10_000, 0)  # $0.004
    with pytest.raises(BudgetExceeded):
        b.check_llm()
    with pytest.raises(BudgetExceeded):
        b.check_speech(10)


def test_speech_caps(tmp_path):
    b = budget(tmp_path)
    b.check_speech(40_000)  # $0.88, under the $1 cap
    b.record_speech("k", 40_000)
    with pytest.raises(BudgetExceeded):
        b.check_speech(10_000)  # would pass $1
    with pytest.raises(BudgetExceeded):
        budget(tmp_path, enforce_cap=False, run_max_chars=100).check_speech(101)


# --- speech ------------------------------------------------------------------------------------------------
def test_ssml_is_well_formed_with_pauses_emphasis_and_rate(monkeypatch):
    monkeypatch.setattr("agents.config.SSML_PAUSES", True)
    monkeypatch.setattr("agents.config.SSML_EMPHASIS", True)
    d = VoiceDirection(moment_id="m", mode="casual", lang="en", pauses=[0, 4], emphasis=["GOAL", "3-2"], rate="fast")
    ssml = build_ssml("GOAL! Lima fires it home, and Azure lead 3-2!", "en-GB-Ollie:DragonHDLatestNeural", "en", d)
    root = ET.fromstring(ssml)
    assert root.attrib["{http://www.w3.org/XML/1998/namespace}lang"] == "en-GB"
    assert ssml.count("<break") == 2 and ssml.count("<emphasis") == 2 and "express-as" not in ssml
    assert ET.fromstring(build_ssml("Lima & co <3", "v", "es")).tag.endswith("}speak")  # markup characters are escaped
    assert "es-MX" in build_ssml("¡GOL!", "es-MX-Jorge:DragonHDLatestNeural", "es")


def test_clip_hash_depends_on_text_voice_and_ssml_only():
    assert clip_hash("a", "v", "s") == clip_hash("a", "v", "s") != clip_hash("a", "v2", "s") != clip_hash("b", "v", "s")


def test_clip_helpers():
    assert duration_of(b"x" * 24000) == 4.0
    assert looks_like_mp3(b"ID3\x04") and looks_like_mp3(b"\xff\xfbrest") and not looks_like_mp3(b"<html>")


REAL_CLIENT = httpx.AsyncClient  # captured once, so a second patch in the same test doesn't wrap the first


def _client(monkeypatch, handler):
    monkeypatch.setattr("agents.speech.httpx.AsyncClient", lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))


def test_synth_writes_a_clip_once_and_reuses_it(tmp_path, monkeypatch):
    calls = []

    def handler(request):
        calls.append(request.headers["Ocp-Apim-Subscription-Key"] and request.content)
        return httpx.Response(200, content=b"ID3" + b"x" * 24000)

    _client(monkeypatch, handler)
    b = budget(tmp_path)
    speech = SpeechClient(LIVE, b, tmp_path / "audio")
    clip = asyncio.run(speech.synth("Hello there", "v", "<speak/>", key="k"))
    again = asyncio.run(speech.synth("Hello there", "v", "<speak/>", key="k"))
    assert clip == again and len(calls) == 1 and (tmp_path / "audio" / f"{clip.audio_hash}.mp3").is_file()
    assert clip.audio_url == f"/audio/{clip.audio_hash}.mp3" and b.totals().chars == len("Hello there")  # billed once, by spoken characters


def test_synth_errors_and_cap(tmp_path, monkeypatch):
    _client(monkeypatch, lambda request: httpx.Response(401, text="denied"))
    with pytest.raises(SpeechError):
        asyncio.run(SpeechClient(LIVE, budget(tmp_path), tmp_path / "a").synth("x", "v", "s", key="k"))
    _client(monkeypatch, lambda request: httpx.Response(200, content=b"not audio"))
    with pytest.raises(SpeechError):
        asyncio.run(SpeechClient(LIVE, budget(tmp_path), tmp_path / "a").synth("x", "v", "s", key="k"))
    capped = dataclasses.replace(LIVE, live_cap_usd=0.0)
    with pytest.raises(BudgetExceeded):
        asyncio.run(SpeechClient(capped, budget(tmp_path, capped), tmp_path / "a").synth("x", "v", "s", key="k"))


# --- settings ----------------------------------------------------------------------------------------------
def test_settings_parse_and_never_crash_on_missing_values():
    s = load_settings(env={"AZURE_OPENAI_ENDPOINT": "https://r.services.ai.azure.com/openai/v1/responses", "LLM_PRICE_IN_PER_1M": "0.40",
                           "LIVE_CAP_USD": "abc", "SPEECH_VOICE_ES_CASUAL": "es-MX-Jorge:DragonHDLatestNeural"}, env_file=None)
    assert s.llm_base_url == "https://r.services.ai.azure.com/openai/v1/"  # only the host is used
    assert s.live_cap_usd == 0.0 and not s.llm_live_allowed and s.voice("casual", "es") == "es-MX-Jorge:DragonHDLatestNeural"
    empty = load_settings(env={}, env_file=None)
    assert empty.health()["llm_configured"] is False
    assert empty.persist == empty.data_dir  # runtime writes default to data/
    mounted = load_settings(env={"PERSIST_DIR": "/mnt/cache"}, env_file=None)
    assert mounted.persist == Path("/mnt/cache") and mounted.data_dir != mounted.persist


def test_health_reports_a_missing_price_but_never_a_value():
    h = dataclasses.replace(LIVE, llm_price_out=0.0).health()
    assert h["llm_price_missing"] is True and h["llm_live_generation"] is False
    assert "k" not in str(h.values()) or all(not isinstance(v, str) for v in h.values())
    assert "api_key" not in repr(LIVE)  # keys are hidden from repr


def test_ssml_spells_out_units_for_the_voice():
    from agents.speech import build_ssml

    en = build_ssml("Lima covers 4.7 km, shot at 79 km/h, 12 m out.", "v", "en")
    assert "4.7 kilometres," in en and "79 kilometres per hour," in en and "12 metres out" in en and ">km" not in en
    es = build_ssml("Lima lleva 11.0 km.", "v", "es")
    assert "11.0 kilómetros." in es
    assert "marks a man." in build_ssml("Lima marks a man.", "v", "en")  # a bare "m" is left alone


def test_ssml_has_no_pauses_or_emphasis_by_default():
    d = VoiceDirection(moment_id="m", mode="casual", lang="en", pauses=[0, 2], emphasis=["GOAL"], rate="fast")
    ssml = build_ssml("GOAL! Lima scores again", "v", "en", d)
    assert "<break" not in ssml and "<emphasis" not in ssml and "<prosody" not in ssml


def test_ssml_wraps_the_line_in_the_chosen_style(monkeypatch):
    d = VoiceDirection(moment_id="m", mode="casual", lang="en", style="ecstatic")
    root = ET.fromstring(build_ssml("Goal! Lima scores", "v", "en", d))
    style = root.find(".//{https://www.w3.org/2001/mstts}express-as")
    assert style is not None and style.attrib["style"] == "ecstatic" and style.text == "Goal! Lima scores"
    assert "express-as" not in build_ssml("Goal!", "v", "en", VoiceDirection(moment_id="m", mode="casual", lang="en", style="default"))
    monkeypatch.setattr("agents.config.STYLE_SYNTAX", "bracket")
    assert "[ecstatic] Goal!" in build_ssml("Goal!", "v", "en", d)
    monkeypatch.setattr("agents.config.STYLE_LANGS", ("en",))
    assert "express-as" not in build_ssml("¡Gol!", "v", "es", VoiceDirection(moment_id="m", mode="casual", lang="es", style="ecstatic"))


def test_a_damaged_ledger_line_is_skipped_not_fatal(tmp_path):
    b = budget(tmp_path)
    b.record_llm("k", 1_000_000, 0)  # $0.40
    with (tmp_path / "ledger.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"kind": "llm", "usd": 0.1\n\n')  # a write cut short, and a blank line
    assert budget(tmp_path).totals().usd == pytest.approx(0.4)


def test_a_damaged_clip_on_disk_is_made_again(tmp_path, monkeypatch):
    calls = []
    _client(monkeypatch, lambda request: calls.append(1) or httpx.Response(200, content=b"ID3" + b"x" * 24000))
    speech = SpeechClient(LIVE, budget(tmp_path), tmp_path / "audio")
    (tmp_path / "audio").mkdir()
    (tmp_path / "audio" / f"{clip_hash('Hi', 'v', 's')}.mp3").write_bytes(b"")  # cut short by a restart
    clip = asyncio.run(speech.synth("Hi", "v", "s", key="k"))
    assert calls == [1] and (tmp_path / "audio" / f"{clip.audio_hash}.mp3").stat().st_size > 0
    assert not list((tmp_path / "audio").glob("*.tmp"))
