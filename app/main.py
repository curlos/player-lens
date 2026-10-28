"""FastAPI backend (specs/agents-backend.md, "Backend endpoints"). No auth, no sessions, no SSE.

Routes: /health, /matches, /data/matches/<id>/<file>.json, /commentary, /audio/<hash>.mp3, /agents/trace, /recap.
A chunk is served from the pre-generated files, then the on-demand cache, then generated (only under the
all-time live cap; the caller gets 202 "preparing" while it runs), and otherwise as template lines. There is no
per-visitor rate limit (owner, Oct 27): each chunk is generated once and cached, so spend has a ceiling, and the
viewer only asks for commentary at 1x.
Run: ``uvicorn app.main:app`` (one worker: the generation locks and the cached spend totals live in this process).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from agents.inputs import build_plan, load_match
from agents.llm import LLM, FoundryLLM
from agents.models import Recap
from agents.recap import build_recap, recap_facts, template_recap
from agents.service import CommentaryService, NotStored
from agents.speech import SpeechClient
from app.budget import Budget, BudgetExceeded
from app.cache import Store
from app.settings import Settings, load_settings
from sim.library import BACKUPS, LIBRARY

log = logging.getLogger("player_lens")
RETRY_AFTER_S = 3
DATA_FILES = {"meta", "events", "ratings", "positions"}
MAX_TEMPLATE_TRACES = 4000  # template chunks are not stored, so their traces are kept in memory (oldest dropped)
FAILED_RETRY_S = 60  # after a failed generation, serve templates for this long before trying that chunk again
MAX_LIVE_ATTEMPTS = 3  # after this many failures a chunk or recap stays on templates (until a restart), so it is not paid for forever


def create_app(settings: Settings | None = None, *, llm: LLM | None = None, speech: SpeechClient | None = None) -> FastAPI:
    """Builds the app. Tests pass fakes for ``llm`` and ``speech``; production builds them from the settings."""
    s = settings or load_settings()
    logging.basicConfig(level=s.log_level)
    for noisy in ("agent_framework", "httpx", "httpx2", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    store = Store(s.data_dir, s.persist)
    budget = Budget(s)
    if llm is None and s.llm_live_allowed:
        llm = FoundryLLM(s, budget)
    if speech is None and s.speech_configured:
        speech = SpeechClient(s, budget, store.audio_ondemand, [store.audio_pre])
    service = CommentaryService(s, budget, store, llm=llm, speech=speech)

    app = FastAPI(title="Player Lens", docs_url=None, redoc_url=None)
    if s.allowed_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(s.allowed_origins), allow_methods=["GET"])

    inflight: dict[tuple, asyncio.Task] = {}
    failed: dict[tuple, float] = {}
    attempts: dict[tuple, int] = {}  # failed generations per key
    template_traces: OrderedDict[str, dict] = OrderedDict()

    def library_ids() -> list[str]:
        return [m.match_id for m in LIBRARY]

    def require(match: str, player: str) -> None:
        if match not in library_ids() or not service.known(match, player):  # the listed matches only (not the hidden backup)
            raise HTTPException(404, "unknown match or player")

    def may_generate(key: tuple) -> bool:
        """Live generation is on, under the cap, and the chunk has not just failed."""
        if service.llm.__class__.__name__ == "OffLLM" or not s.llm_live_allowed:
            return False
        try:
            budget.check_llm()
        except BudgetExceeded:
            return False
        if attempts.get(key, 0) >= MAX_LIVE_ATTEMPTS:
            return False
        return time.monotonic() - failed.get(key, -FAILED_RETRY_S) >= FAILED_RETRY_S

    def start(key: tuple, coro) -> None:
        async def run() -> None:
            try:
                await coro
            except NotStored as err:  # a fallback is never cached: templates for now, and the chunk is tried again later
                log.warning("%s", err)
                failed[key] = time.monotonic()
                attempts[key] = attempts.get(key, 0) + 1
            except Exception:  # a failed generation must never take the server down; the visitor gets templates instead
                log.exception("generation failed for %s", key)
                failed[key] = time.monotonic()
                attempts[key] = attempts.get(key, 0) + 1
            finally:
                inflight.pop(key, None)

        inflight[key] = asyncio.create_task(run())

    preparing = JSONResponse({"status": "preparing", "retry_after": RETRY_AFTER_S}, status_code=202)

    @app.get("/health")
    def health() -> dict:
        return s.health()

    @app.get("/matches")
    def matches() -> list[dict]:
        out = []
        for info in LIBRARY:  # the backup hero stays hidden
            meta = json.loads((s.data_dir / "matches" / info.match_id / "meta.json").read_text(encoding="utf-8"))
            home, away = meta["teams"]
            out.append({"match_id": meta["match_id"], "label": meta["label"], "blurb": meta.get("blurb"), "matchday": meta["matchday"],
                        "home": home["abbr"], "away": away["abbr"], "score": meta["score"], "hero": meta["hero"]})
        return out

    @app.get("/data/matches/{match_id}/{name}.json")
    def match_file(match_id: str, name: str):
        known = library_ids() + [m.match_id for m in BACKUPS]
        if match_id not in known or name not in DATA_FILES:
            raise HTTPException(404, "not found")
        return FileResponse(s.data_dir / "matches" / match_id / f"{name}.json", media_type="application/json",
                            headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/commentary")
    async def commentary(
        match: str, player: str = Query(pattern=r"^[a-z]{3}_\d{2}$"), mode: Literal["casual", "analyst"] = "casual",
        lang: Literal["en", "es"] = "en", chunk: int = Query(ge=0, le=89),
    ):
        require(match, player)
        cached = store.read_chunk(match, player, mode, lang, chunk)
        if cached:
            return cached
        key = (match, player, mode, lang, chunk)
        if key in inflight:
            return preparing
        if may_generate(key):
            start(key, service.generate(match, player, chunk, [(mode, lang)]))
            return preparing
        body, traces = await service.template_chunk(match, player, mode, lang, chunk)
        for line_id, trace in traces.items():
            template_traces[line_id] = trace.model_dump(exclude_none=True)
        while len(template_traces) > MAX_TEMPLATE_TRACES:
            template_traces.popitem(last=False)
        return body

    @app.get("/audio/{audio_hash}.mp3")
    def audio(audio_hash: str):
        path = store.audio_path(audio_hash)
        if path is None:
            raise HTTPException(404, "not found")
        return FileResponse(path, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})

    @app.get("/agents/trace")
    def trace(line: str):
        found = store.read_trace(line) or template_traces.get(line)
        if not found:
            raise HTTPException(404, "no trace for that line")
        return found

    @app.get("/recap")
    async def recap(
        match: str, player: str = Query(pattern=r"^[a-z]{3}_\d{2}$"), mode: Literal["casual", "analyst"] = "casual",
        lang: Literal["en", "es"] = "en",
    ):
        require(match, player)
        cached = store.read_recap(match, player, mode, lang)
        if cached:
            return cached
        key = (match, player, mode, lang, "recap")
        if key in inflight:
            return preparing
        if may_generate(key):
            async def make() -> None:
                bundle = load_match(s.data_dir, match)
                recap, complete = await build_recap(bundle, s.data_dir, player, mode, lang, service.llm, service.speech, s.voice(mode, lang))
                if not complete:
                    raise NotStored(f"{match}.{player}.recap_{mode}_{lang} is a fallback; not cached")
                store.write_recap(match, player, mode, lang, recap, "ondemand")

            start(key, make())
            return preparing
        bundle = load_match(s.data_dir, match)
        facts = recap_facts(bundle, player, build_plan(s.data_dir, match, player).facts)
        return Recap(text=template_recap(facts, lang)).model_dump(mode="json")

    dist = Path(__file__).resolve().parent.parent / "web" / "dist"
    if dist.is_dir():  # the built frontend (Phase 4 packages this into the image); /audio/crowd/* comes from here
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")

    app.state.service = service
    return app


app = create_app()
