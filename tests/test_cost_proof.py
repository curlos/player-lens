"""Proof that cached commentary costs nothing: the real pre-generated hero files never call the model or Speech, and any
other player's minute is generated once, then served from the persist folder (the Azure Files share in production),
also after a restart. Fake model and fake Speech count every call; nothing touches Azure."""

import time

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from tests.conftest import MATCH, ROOT, STAR
from tests.fakes import FakeLLM, FakeSpeech

VARIANTS = [(m, lang) for m in ("casual", "analyst") for lang in ("en", "es")]
OTHER = "rdm_03"  # Ferreira: never pre-generated


def live_app(share, llm, speech):
    """The real data/ folder (Lima's stored files, read-only) with live generation ON and runtime writes in ``share``."""
    s = Settings(openai_endpoint="https://x.services.ai.azure.com/", openai_api_key="k", openai_deployment="m", llm_price_in=0.4,
                 llm_price_out=1.6, live_cap_usd=130.0, speech_key="k", speech_region="eastus", data_dir=ROOT / "data", persist_dir=share,
                 voices={f"{lang}_{mode}": "v" for lang in ("en", "es") for mode in ("casual", "analyst")})
    return TestClient(create_app(s, llm=llm, speech=speech))


def wait_ready(c, params):
    for _ in range(200):
        r = c.get("/commentary", params=params)
        if r.status_code != 202:
            return r
        time.sleep(0.05)
    raise AssertionError("still preparing")


def test_lima_whole_match_makes_no_ai_calls_even_with_live_generation_on(tmp_path):
    llm, speech = FakeLLM(), FakeSpeech()
    with live_app(tmp_path / "share", llm, speech) as c:
        for mode, lang in VARIANTS:
            for chunk in range(90):
                r = c.get("/commentary", params=dict(match=MATCH, player=STAR, mode=mode, lang=lang, chunk=chunk))
                assert r.status_code == 200 and r.json()["status"] == "ready", (mode, lang, chunk)
                assert all(ln["audio_url"] for ln in r.json()["lines"]), (mode, lang, chunk)  # stored with its voice clip
            assert c.get("/recap", params=dict(match=MATCH, player=STAR, mode=mode, lang=lang)).status_code == 200
    assert llm.calls == [] and speech.said == []  # 360 minutes and 4 recaps: zero model calls, zero voice calls
    assert not (tmp_path / "share").exists()  # nothing written, nothing paid for


def test_another_player_is_generated_once_then_free_even_after_a_restart(tmp_path):
    share = tmp_path / "share"  # stands in for the Azure Files mount
    q = dict(match=MATCH, player=OTHER, mode="casual", lang="en", chunk=30)

    first_llm, first_speech = FakeLLM(), FakeSpeech()
    with live_app(share, first_llm, first_speech) as c:
        assert c.get("/commentary", params=q).status_code == 202  # never made before: generated now
        ready = wait_ready(c, q).json()
        paid = (len(first_llm.calls), len(first_speech.said))
        assert paid[0] > 0 and paid[1] > 0
        for _ in range(5):  # the next visitors: served from the share
            assert c.get("/commentary", params=q).json() == ready
        assert (len(first_llm.calls), len(first_speech.said)) == paid
    assert (share / "commentary_ondemand" / MATCH / OTHER / "casual_en_30.json").is_file()

    after_llm, after_speech = FakeLLM(), FakeSpeech()
    with live_app(share, after_llm, after_speech) as c:  # a restart or redeploy: new container, same share
        assert c.get("/commentary", params=q).json() == ready
        assert after_llm.calls == [] and after_speech.said == []

        other_version = {**q, "lang": "es"}  # each version is its own cache entry, generated once too
        assert c.get("/commentary", params=other_version).status_code == 202
        wait_ready(c, other_version)
        assert after_llm.calls
