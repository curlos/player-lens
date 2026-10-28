"""Commentary contracts the backend serves (specs/agents-backend.md, "Backend endpoints" and "Trace data").

Exported to contracts/commentary_chunk.schema.json, contracts/commentary_preparing.schema.json and
contracts/trace.schema.json. The per-agent input/output models (Spec: Agents and Backend, "Agent
contracts") follow: every agent's output is validated against one of them before the next agent runs.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


Mode = Literal["casual", "analyst"]
Lang = Literal["en", "es"]
FactCheck = Literal["pass", "fixed", "removed", "template"]


class CommentaryLine(Strict):
    """One line, shaped so a studio could render it as a synchronized overlay."""

    id: str = Field(min_length=1)  # stable line_id used by GET /agents/trace
    t: float = Field(ge=0, le=5400)  # match seconds when the line starts
    duration: float = Field(ge=0)  # seconds on screen / clip length
    player: str = Field(pattern=r"^[a-z]{3}_\d{2}$")
    type: str = Field(min_length=1)  # the moment trigger
    importance: float = Field(ge=0, le=1)
    text: str = Field(min_length=1)
    audio_url: str | None = None
    fact_check: FactCheck


class CommentaryChunk(Strict):
    """GET /commentary response for one cached 1-minute chunk."""

    match: str
    player: str = Field(pattern=r"^[a-z]{3}_\d{2}$")
    mode: Mode
    lang: Lang
    chunk: int = Field(ge=0, le=89)
    status: Literal["ready"] = "ready"
    lines: list[CommentaryLine]


class ChunkPreparing(Strict):
    """GET /commentary 202 response while a chunk is generating."""

    status: Literal["preparing"] = "preparing"
    retry_after: int = Field(ge=1)


class TraceStep(Strict):
    """One agent's step in "How this was made". Fields beyond ``agent`` depend on the agent."""

    agent: Literal["Interpreter", "Moments", "Commentator", "Fact Guard", "Personalizer", "Voice", "Template"]
    summary: str | None = None
    fact_ids: list[str] | None = None
    why: str | None = None
    text: str | None = None
    fact_check: FactCheck | None = None
    issues: list[str] | None = None
    before: str | None = None
    after: str | None = None
    mode: Mode | None = None
    lang: Lang | None = None
    duration_s: float | None = None
    style: str | None = None
    reason: Literal["cap", "failure"] | None = None


class Trace(Strict):
    """GET /agents/trace response."""

    line_id: str
    steps: list[TraceStep] = Field(min_length=1)
    events: list[str]


# --- Per-agent contracts (specs/agents-backend.md, "Agent contracts") -------------------------------

FactKind = Literal[
    "goal", "shot", "key_pass", "tackle", "foul", "card", "rating_change", "pressure_regain", "counterpress",
    "recovery_run", "marking_denial", "decoy_run", "spell", "filler_stat", "play",
]
Tone = Literal["calm", "building", "excited", "tense", "relieved", "analytical"]
Rate = Literal["slow", "normal", "fast"]
GuardOutcome = Literal["pass", "fixed", "removed"]


class Fact(Strict):
    """One code-built fact the commentary may cite. Numbers and names live only in ``values``."""

    fact_id: str = Field(min_length=1)
    t: float = Field(ge=0, le=5400)
    kind: FactKind
    player_id: str = Field(pattern=r"^[a-z]{3}_\d{2}$")
    # Every fact cites an event or rating-log id, except filler_stat and spell (a stat key such as "spell:17").
    event_ids: list[str]
    values: dict[str, str | int | float | bool] = Field(default_factory=dict)
    label: str = ""  # a short neutral phrase from the Interpreter LLM (max 12 words), no number or name outside values


class Moment(Strict):
    """A scheduled commentary moment: when code decided a line happens, plus the LLM's tone and reason."""

    moment_id: str = Field(min_length=1)
    t: float = Field(ge=0, le=5400)
    trigger: str = Field(min_length=1)  # goal, card, key_event, rating_change, off_ball, reaction, filler
    importance: float = Field(ge=0, le=1)  # always from code
    tone: Tone = "calm"
    fact_ids: list[str] = Field(min_length=1)
    why: str = ""  # one sentence for the trace


class CanonicalLine(Strict):
    """The Commentator's one neutral English line for a moment."""

    moment_id: str
    text: str = Field(min_length=1)
    fact_ids_used: list[str] = Field(default_factory=list)


class GuardResult(Strict):
    """Fact Guard's verdict on one line. ``before`` and ``after`` are set only when it fixed the line."""

    moment_id: str
    text: str  # the line to use (empty when removed)
    fact_check: GuardOutcome
    issues: list[str] = Field(default_factory=list)
    before: str | None = None
    after: str | None = None


class Variant(Strict):
    """The Personalizer's version of a checked line for one mode and language."""

    moment_id: str
    mode: Mode
    lang: Lang
    text: str = Field(min_length=1)


class VoiceDirection(Strict):
    """The Voice Director's speaking instructions for one variant; code turns them into SSML."""

    moment_id: str
    mode: Mode
    lang: Lang
    pauses: list[int] = Field(default_factory=list)  # word indexes after which to pause (commas, sentence ends)
    emphasis: list[str] = Field(default_factory=list, max_length=2)
    rate: Rate = "normal"
    style: str = "default"


class Recap(Strict):
    """GET /recap response: the full-time paragraph for one player, mode and language."""

    text: str = Field(min_length=1)
    audio_url: str | None = None
    duration_s: float | None = None
