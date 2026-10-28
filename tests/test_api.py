"""Backend endpoints with a fake model and fake Speech (no live calls): routes, validation, cache order, 202 flow, caps."""

import dataclasses
import time

import pytest
from fastapi.testclient import TestClient

from agents.models import CommentaryChunk
from app.budget import Budget
from app.main import create_app
from app.settings import Settings
from tests.conftest import MATCH, STAR
from tests.fakes import FakeLLM, FakeSpeech

Q = dict(match=MATCH, player=STAR, mode="casual", lang="en", chunk=88)


def settings(scratch, **kw) -> Settings:
    base = Settings(openai_endpoint="https://x.services.ai.azure.com/", openai_api_key="k", openai_deployment="m", llm_price_in=0.4,
                    llm_price_out=1.6, live_cap_usd=1.0, data_dir=scratch,
                    voices={f"{lang}_{mode}": "v" for lang in ("en", "es") for mode in ("casual", "analyst")})
    return dataclasses.replace(base, **kw)


def client(scratch, llm=None, **kw) -> TestClient:
    return TestClient(create_app(settings(scratch, **kw), llm=llm or FakeLLM(), speech=FakeSpeech()))


def wait_ready(c, params, tries=100):
    for _ in range(tries):
        r = c.get("/commentary", params=params)
        if r.status_code != 202:
            return r
        time.sleep(0.05)
    raise AssertionError("still preparing")


# --- static data and validation -------------------------------------------------------------------------
def test_health_never_reveals_values(scratch):
    h = client(scratch).get("/health").json()
    assert h["ok"] and h["llm_live_generation"] is True and all(isinstance(v, bool) for v in h.values())


def test_matches_lists_the_library_and_hides_the_backup(scratch):
    rows = client(scratch).get("/matches").json()
    assert [r["match_id"] for r in rows] == ["md38_title_decider", "md19_blowout", "md27_draw"]
    assert rows[0]["hero"] and rows[0]["home"] == "AZC" and rows[0]["score"] == {"azc": 3, "rdm": 2}


def test_match_files_are_served_with_cache_headers_and_nothing_else(scratch):
    c = client(scratch)
    for name in ("meta", "events", "ratings", "positions"):
        r = c.get(f"/data/matches/{MATCH}/{name}.json")
        assert r.status_code == 200 and "max-age" in r.headers["cache-control"]
    assert c.get(f"/data/matches/{MATCH}/world.json").status_code == 404
    assert c.get("/data/matches/nope/meta.json").status_code == 404
    assert c.get("/data/matches/..%2F..%2F.env/meta.json").status_code == 404


@pytest.mark.parametrize("change", [{"mode": "x"}, {"lang": "fr"}, {"chunk": 90}, {"chunk": -1}, {"chunk": "a"}, {"player": "bad"}])
def test_invalid_parameters_are_422(scratch, change):
    assert client(scratch).get("/commentary", params={**Q, **change}).status_code == 422


def test_unknown_match_or_player_is_404(scratch):
    c = client(scratch)
    assert c.get("/commentary", params={**Q, "match": "nope"}).status_code == 404
    assert c.get("/commentary", params={**Q, "player": "xyz_99"}).status_code == 404
    assert c.get("/recap", params={"match": "nope", "player": STAR}).status_code == 404


# --- lookup order, 202 flow -------------------------------------------------------------------------------
def test_generation_answers_202_then_the_ready_chunk_and_it_is_cached(scratch):
    llm = FakeLLM(delay=0.05)
    with client(scratch, llm) as c:
        first = c.get("/commentary", params=Q)
        assert first.status_code == 202 and first.json() == {"status": "preparing", "retry_after": 3}
        ready = wait_ready(c, Q)
        body = CommentaryChunk.model_validate(ready.json())
        from agents.inputs import build_plan

        expected = len(build_plan(scratch, MATCH, STAR).chunk_moments(88))
        assert body.status == "ready" and body.chunk == 88 and len(body.lines) == expected and all(ln.audio_url for ln in body.lines)
        calls = len(llm.calls)
        assert c.get("/commentary", params=Q).json() == ready.json() and len(llm.calls) == calls  # served from disk, no new calls
        assert (scratch / "commentary_ondemand" / MATCH / STAR / "casual_en_88.json").is_file()


def test_on_demand_chunks_go_to_the_persist_folder_and_survive_a_restart(scratch, tmp_path):
    share = tmp_path / "share"  # stands in for the Azure Files mount
    with client(scratch, FakeLLM(), persist_dir=share) as c:
        assert c.get("/commentary", params=Q).status_code == 202
        ready = wait_ready(c, Q).json()
    assert (share / "commentary_ondemand" / MATCH / STAR / "casual_en_88.json").is_file()
    assert not (scratch / "commentary_ondemand").exists()  # nothing written beside the baked files
    restarted = FakeLLM()
    with client(scratch, restarted, persist_dir=share) as c:  # a new container, same share
        assert c.get("/commentary", params=Q).json() == ready and restarted.calls == []  # paid for once


def test_ten_viewers_requesting_one_chunk_cause_one_generation(scratch):
    llm = FakeLLM(delay=0.1)
    with client(scratch, llm) as c:
        statuses = [c.get("/commentary", params=Q).status_code for _ in range(10)]
        assert statuses == [202] * 10
        wait_ready(c, Q)
        assert llm.calls.count("commentator") == 1


def test_pre_generated_files_win_over_on_demand_and_need_no_model(scratch):
    import asyncio

    from agents.inputs import build_plan, load_match
    from agents.pipeline import run_chunk
    from app.cache import Store

    store = Store(scratch)
    result = asyncio.run(run_chunk(load_match(scratch, MATCH), build_plan(scratch, MATCH, STAR), 88, [("casual", "en")], FakeLLM(), None, lambda m, l: ""))
    store.write_chunk(result.chunks[("casual", "en")], result.traces, "pre")
    off = TestClient(create_app(settings(scratch, live_cap_usd=0.0)))  # no model, cap 0
    r = off.get("/commentary", params=Q)
    goal = next(ln for ln in r.json()["lines"] if ln["type"] == "goal")
    assert r.status_code == 200 and goal["fact_check"] == "pass"  # the stored model chunk, not a template
    trace = off.get("/agents/trace", params={"line": goal["id"]})
    assert trace.status_code == 200 and [s["agent"] for s in trace.json()["steps"]][:2] == ["Interpreter", "Moments"]


# --- caps and fallbacks ------------------------------------------------------------------------------------
def test_cap_zero_serves_template_lines_and_a_template_trace(scratch):
    llm = FakeLLM()
    c = client(scratch, llm, live_cap_usd=0.0)
    r = c.get("/commentary", params=Q)
    assert r.status_code == 200 and llm.calls == []
    chunk = CommentaryChunk.model_validate(r.json())
    assert all(ln.fact_check == "template" and ln.audio_url is None for ln in chunk.lines)
    trace = c.get("/agents/trace", params={"line": chunk.lines[0].id}).json()
    assert [s["agent"] for s in trace["steps"]] == ["Template"] and trace["steps"][0]["reason"] == "cap"


def test_a_missing_price_keeps_live_generation_off(scratch):
    c = client(scratch, llm_price_in=0.0)
    assert c.get("/health").json()["llm_price_missing"] is True
    assert c.get("/commentary", params=Q).status_code == 200


def test_todays_spend_at_the_cap_stops_generation(scratch):
    s = settings(scratch)
    Budget(s).record_llm("earlier", 2_000_000, 500_000)  # $1.60, over the $1 cap, in the ledger on disk
    r = TestClient(create_app(s, llm=FakeLLM(), speech=FakeSpeech())).get("/commentary", params=Q)
    assert r.status_code == 200 and all(ln["fact_check"] == "template" for ln in r.json()["lines"])


def test_no_per_visitor_rate_limit(scratch):
    with client(scratch, FakeLLM(delay=0.05)) as c:
        codes = [c.get("/commentary", params={**Q, "chunk": n}).status_code for n in (10, 11, 12, 13, 14)]
        assert codes == [202] * 5  # every uncached chunk is generated; the all-time cap is the only spend limit


def test_a_crashing_generation_never_takes_the_server_down(scratch):
    with client(scratch, FakeLLM(explode=True)) as c:
        assert c.get("/commentary", params=Q).status_code == 202
        r = wait_ready(c, Q)
        assert r.status_code == 200 and all(ln["fact_check"] == "template" for ln in r.json()["lines"])  # templates for the next minute
        assert c.get("/health").status_code == 200


# --- audio, trace, recap -------------------------------------------------------------------------------------
def test_audio_route(scratch):
    h = "ab" * 16
    (scratch / "audio").mkdir()
    (scratch / "audio" / f"{h}.mp3").write_bytes(b"ID3" + b"x" * 100)
    c = client(scratch)
    r = c.get(f"/audio/{h}.mp3")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and "immutable" in r.headers["cache-control"]
    assert c.get("/audio/" + "0" * 32 + ".mp3").status_code == 404 and c.get("/audio/not-a-hash.mp3").status_code == 404
    od = scratch / "commentary_ondemand" / "audio"
    od.mkdir(parents=True)
    (od / f"{'cd' * 16}.mp3").write_bytes(b"ID3")
    assert c.get(f"/audio/{'cd' * 16}.mp3").status_code == 200  # on-demand audio is served from the same URL space


def test_trace_route_rejects_bad_ids(scratch):
    c = client(scratch)
    for bad in ("", "a.b.c", f"{MATCH}.{STAR}.casual.en.88.99", f"{MATCH}.{STAR}.casual.en.x.1", "../../etc.passwd.x.y.1.2"):
        assert c.get("/agents/trace", params={"line": bad}).status_code == 404


def test_recap_template_then_generated_and_cached(scratch):
    off = client(scratch, live_cap_usd=0.0)
    r = off.get("/recap", params=dict(match=MATCH, player=STAR, mode="analyst", lang="en"))
    assert r.status_code == 200 and "8.9" in r.json()["text"] and r.json()["audio_url"] is None
    with client(scratch) as c:
        params = dict(match=MATCH, player=STAR, mode="casual", lang="es")
        assert c.get("/recap", params=params).status_code == 202
        for _ in range(100):
            got = c.get("/recap", params=params)
            if got.status_code == 200:
                break
            time.sleep(0.05)
        assert got.status_code == 200 and set(got.json()) == {"text", "audio_url", "duration_s"}
        assert (scratch / "commentary_ondemand" / MATCH / STAR / "recap_casual_es.json").is_file()


def test_a_fallback_chunk_is_served_but_never_cached(scratch):
    """A failed agent makes template lines: the visitor gets them, but nothing is stored, so the chunk can be tried again."""
    with client(scratch, FakeLLM(fail=("commentator",))) as c:
        assert c.get("/commentary", params=Q).status_code == 202
        r = wait_ready(c, Q)
        assert r.status_code == 200 and r.json()["lines"]
    assert not (scratch / "commentary_ondemand" / MATCH / STAR / "casual_en_88.json").exists()
    with client(scratch, FakeLLM()) as c:  # later, a working model: generated and cached this time
        assert c.get("/commentary", params=Q).status_code == 202
        wait_ready(c, Q)
    assert (scratch / "commentary_ondemand" / MATCH / STAR / "casual_en_88.json").is_file()


def test_a_template_recap_is_never_cached(scratch):
    params = dict(match=MATCH, player=STAR, mode="casual", lang="en")
    with client(scratch, FakeLLM(fail=("recap",))) as c:
        assert c.get("/recap", params=params).status_code == 202
        for _ in range(100):
            got = c.get("/recap", params=params)
            if got.status_code == 200:
                break
            time.sleep(0.05)
        assert got.status_code == 200 and "8.9" in got.json()["text"]  # the template
    assert not (scratch / "commentary_ondemand" / MATCH / STAR / "recap_casual_en.json").exists()


def test_trace_lookup_rejects_unknown_mode_and_language(scratch):
    from app.cache import Store

    store = Store(scratch)
    assert store.read_trace(f"{MATCH}.{STAR}.x.en.88.0") is None and store.read_trace(f"{MATCH}.{STAR}.casual.fr.88.0") is None


@pytest.mark.parametrize("agent", ["personalizer", "voice_director"])
def test_a_spanish_chunk_with_a_failed_personalizer_or_voice_director_is_not_cached(scratch, agent):
    q = {**Q, "lang": "es"}
    with client(scratch, FakeLLM(fail=(agent,))) as c:
        assert c.get("/commentary", params=q).status_code == 202
        assert wait_ready(c, q).status_code == 200
    assert not (scratch / "commentary_ondemand" / MATCH / STAR / "casual_es_88.json").exists()


def test_a_chunk_that_keeps_failing_stops_trying_after_three_attempts(scratch, monkeypatch):
    monkeypatch.setattr("app.main.FAILED_RETRY_S", 0)  # no wait between attempts
    llm = FakeLLM(fail=("commentator",))
    with client(scratch, llm) as c:
        for _ in range(40):  # a viewer keeps asking; each ask after a failure may start a new attempt
            c.get("/commentary", params=Q)
            time.sleep(0.02)
        attempts = llm.calls.count("interpreter")  # one Interpreter call per attempt
        assert attempts == 3
        assert c.get("/commentary", params=Q).status_code == 200  # templates now, and no further paid attempt
        assert llm.calls.count("interpreter") == attempts


@pytest.mark.parametrize("match", ["md38_title_decider_backup", "md19_blowout/../md27_draw"])
def test_only_listed_matches_are_served_commentary(scratch, match):
    c = client(scratch)
    assert c.get("/commentary", params={**Q, "match": match}).status_code == 404
    assert c.get("/recap", params={"match": match, "player": STAR}).status_code == 404
