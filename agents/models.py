"""Commentary contracts the backend serves (specs/agents-backend.md, "Backend endpoints" and "Trace data").

Exported to contracts/commentary_chunk.schema.json, contracts/commentary_preparing.schema.json and
contracts/trace.schema.json. The per-agent
input/output models (facts, moments, lines) are added with the agent pipeline.
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
