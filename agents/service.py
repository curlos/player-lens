"""Chunk generation with every fallback in one place (specs/agents-backend.md, "Caching, cap and fallback").

``generate`` runs the pipeline for the requested variants and stores the result. With no model configured, or once
a spend limit is reached, the same pipeline produces template lines (marked "cap" in the trace) and no audio, so a
caller always gets a valid chunk. The on-demand server asks for one (mode, lang); the offline pre-generation asks for all four.
"""

from __future__ import annotations

from typing import Any

from agents.inputs import build_plan, load_match
from agents.llm import LLM
from agents.models import Trace
from agents.pipeline import ChunkResult, Key, run_chunk
from agents.speech import SpeechClient
from app.budget import Budget, BudgetExceeded
from app.cache import Store
from app.settings import Settings


class NotStored(Exception):
    """The model or the voice did not fully produce this chunk or recap (a spend limit or a failed call), so it is not cached:
    a template stand-in must never be stored as if the agents wrote it, and the next request may try again."""


class OffLLM:
    """Stands in when no model is configured: every call is refused, so each role falls back to templates."""

    async def complete(self, agent: str, payload: dict[str, Any], *, key: str) -> dict[str, Any]:
        raise BudgetExceeded("no model configured")


class CommentaryService:
    def __init__(self, settings: Settings, budget: Budget, store: Store, *, llm: LLM | None = None, speech: SpeechClient | None = None):
        self.s = settings
        self.budget = budget
        self.store = store
        self.llm = llm or OffLLM()
        self.speech = speech

    def known(self, match: str, player: str) -> bool:
        """Whether this match and player exist (the backend 404s otherwise)."""
        try:
            return player in load_match(self.s.data_dir, match).players
        except (FileNotFoundError, ValueError):
            return False

    async def generate(
        self, match: str, player: str, chunk: int, variants: list[Key], *, where: str = "ondemand",
        previous_lines: list[str] | None = None, live: bool = True, write: bool = True,
    ) -> ChunkResult:
        """Runs the agents for one chunk and writes every variant to the store. ``live=False`` forces template lines;
        ``write=False`` lets the offline script inspect the result before deciding to store it. Raises NotStored (and
        writes nothing) when the result is a fallback: a limit or a failed call, or a line missing its expected clip."""
        bundle = load_match(self.s.data_dir, match)
        plan = build_plan(self.s.data_dir, match, player)
        result = await run_chunk(
            bundle, plan, chunk, variants, self.llm if live else OffLLM(), self.speech if live else None, self.s.voice, previous_lines,
        )
        if write:
            for mode, lang in variants:
                voiced = live and self.speech is not None and bool(self.s.voice(mode, lang))
                if not result.model_produced() or (voiced and any(not ln.audio_url for ln in result.chunks[(mode, lang)].lines)):
                    raise NotStored(f"{match}.{player}.{mode}.{lang}.{chunk} is a fallback; not cached")
            for key in variants:
                self.store.write_chunk(result.chunks[key], result.traces, where)
        return result

    async def template_chunk(self, match: str, player: str, mode: str, lang: str, chunk: int) -> tuple[dict, dict[str, Trace]]:
        """A template-only chunk (no model, no audio, nothing stored) for when generation is not allowed."""
        bundle = load_match(self.s.data_dir, match)
        plan = build_plan(self.s.data_dir, match, player)
        result = await run_chunk(bundle, plan, chunk, [(mode, lang)], OffLLM(), None, self.s.voice)  # type: ignore[arg-type]
        return result.chunks[(mode, lang)].model_dump(mode="json"), result.traces
