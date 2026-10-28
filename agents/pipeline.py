"""The six-agent commentary pipeline on Microsoft Agent Framework (specs/agents-backend.md, "Pipeline overview").

One workflow run handles one chunk (a match minute of one player) and passes a ``ChunkJob`` down a chain of
executors, one per role:

    Interpreter -> Moments -> Commentator -> Fact Guard -> Personalizer -> Voice Director -> Speech -> Assemble

Each executor's model output is validated against its Pydantic contract before the next one runs. A call that
fails or returns something invalid is retried once; after that the role falls back (default labels and tone,
template lines, default speech directions) and the chunk is still produced. A spend limit (BudgetExceeded)
skips the remaining model calls and the moments fall back to templates, marked "cap" in the trace.
Facts, timing, importance and every number are computed by code (agents/inputs.py); the model only writes words.
"""

from __future__ import annotations

import asyncio
import math
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler
from pydantic import BaseModel, ValidationError
from typing_extensions import Never

from agents import config as C
from agents.fact_guard import check_line, roster_tokens, strip_initials
from agents.inputs import MatchBundle, PlayerPlan, chunk_context, home_side
from agents.llm import LLM, LLMError
from agents.models import (
    CanonicalLine, CommentaryChunk, CommentaryLine, Fact, GuardResult, Moment, Trace, TraceStep, Variant, VoiceDirection,
)
from agents.speech import Clip, SpeechClient, SpeechError, build_ssml
from agents.templates import template_line
from app.budget import BudgetExceeded
from sim.roster import _fold

Key = tuple[str, str]  # (mode, lang)


@dataclass
class ChunkJob:
    """State handed down the chain; each executor fills in its part."""

    bundle: MatchBundle
    plan: PlayerPlan
    chunk: int
    player: str
    variants: list[Key]
    previous_lines: list[str]
    moments: list[Moment] = field(default_factory=list)
    facts: dict[str, Fact] = field(default_factory=dict)
    canonical: dict[str, CanonicalLine] = field(default_factory=dict)
    guard: dict[str, GuardResult] = field(default_factory=dict)
    texts: dict[Key, dict[str, str]] = field(default_factory=dict)  # final text per variant and moment
    is_template: dict[Key, set[str]] = field(default_factory=dict)  # moments whose text is a template line
    directions: dict[Key, dict[str, VoiceDirection]] = field(default_factory=dict)
    clips: dict[Key, dict[str, Clip]] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)  # agent -> what went wrong (for the trace)
    blocked: bool = False  # a spend limit stopped model calls


@dataclass
class ChunkResult:
    """What one chunk run produced: a CommentaryChunk and a trace per line, for every requested variant."""

    chunks: dict[Key, CommentaryChunk]
    traces: dict[str, Trace]
    final_lines: list[str]  # the final English-Casual-or-first-variant texts, the next chunk's previous_lines
    failed: bool = False  # a spend limit stopped a call, or any agent or Speech call failed (job.notes), in any variant

    def model_produced(self) -> bool:
        """False if a spend limit stopped the model or any agent or Speech call failed (a Personalizer or Voice Director
        outage included), so the chunk must not be cached; it stays retryable."""
        steps = [s for t in self.traces.values() for s in t.steps]
        return not self.failed and not any((s.agent == "Template" and s.reason == "cap") or "failed twice" in (s.summary or "") for s in steps)


class AgentFailed(Exception):
    pass


async def ask(llm: LLM, agent: str, payload: dict[str, Any], parse: Callable[[dict[str, Any]], Any], *, key: str) -> Any:
    """One model call whose answer is validated by ``parse``; a failure or invalid answer retries once, then raises AgentFailed."""
    last: Exception | None = None
    for _ in range(2):
        try:
            return parse(await llm.complete(agent, payload, key=key))
        except BudgetExceeded:
            raise
        except (LLMError, ValidationError, ValueError, KeyError, TypeError) as err:
            last = err
    raise AgentFailed(f"{agent} failed twice: {type(last).__name__}")


def _fact_payload(f: Fact, with_label: bool = True) -> dict[str, Any]:
    d: dict[str, Any] = {"fact_id": f.fact_id, "kind": f.kind, "t": f.t, "values": f.values}
    if with_label:
        d["label"] = f.label
    return d


def _moment_payload(job: ChunkJob, m: Moment) -> dict[str, Any]:
    return {"moment_id": m.moment_id, "t": m.t, "trigger": m.trigger, "tone": m.tone, "importance": m.importance,
            "facts": [_fact_payload(job.facts[fid]) for fid in m.fact_ids]}


def _facts_of(job: ChunkJob, m: Moment) -> list[Fact]:
    return [job.facts[fid] for fid in m.fact_ids]


def _words(text: str) -> int:
    return len(text.split())


# --- Executors ---------------------------------------------------------------------------------------


class _Role(Executor):
    """Shared plumbing: every role gets the model client, and records failures on the job."""

    def __init__(self, id: str, llm: LLM):
        super().__init__(id=id)
        self.llm = llm

    async def guarded(self, job: ChunkJob, agent: str, coro: Awaitable[Any]) -> Any:
        """Awaits a model step; on a spend stop or two failures records why and returns None (the role then falls back)."""
        try:
            return await coro
        except BudgetExceeded as err:
            job.blocked = True
            job.notes[agent] = f"stopped by a spend limit: {err}"
        except AgentFailed as err:
            job.notes[agent] = str(err)
        return None


class InterpreterExec(_Role):
    def __init__(self, llm: LLM):
        super().__init__("Interpreter", llm)

    @handler
    async def run(self, job: ChunkJob, ctx: WorkflowContext[ChunkJob]) -> None:
        facts = list(job.facts.values())
        names = roster_tokens(job.bundle)

        def parse(answer: dict[str, Any]) -> dict[str, str]:
            labels = {str(k): str(v).strip() for k, v in answer["labels"].items() if str(k) in job.facts}
            good = {}
            for fid, label in labels.items():  # a label has at most 12 words, no digits and no player names
                tokens = {_fold(t) for t in re.findall(r"[^\W\d_]+", label)}
                if label and _words(label) <= 12 and not re.search(r"\d", label) and not (tokens & names.keys()):
                    good[fid] = label
            return good

        if not job.blocked and facts:
            payload = {"context": chunk_context(job.bundle, job.player, job.chunk), "facts": [_fact_payload(f, False) for f in facts]}
            labels = await self.guarded(job, "Interpreter", ask(self.llm, "interpreter", payload, parse, key=_key(job, "interpreter")))
            for fid, label in (labels or {}).items():
                job.facts[fid] = job.facts[fid].model_copy(update={"label": label})
        await ctx.send_message(job)


class MomentsExec(_Role):
    def __init__(self, llm: LLM):
        super().__init__("Moments", llm)

    @handler
    async def run(self, job: ChunkJob, ctx: WorkflowContext[ChunkJob]) -> None:
        tones = {"calm", "building", "excited", "tense", "relieved", "analytical"}

        def parse(answer: dict[str, Any]) -> dict[str, tuple[str, str]]:
            out = {}
            for item in answer["moments"]:
                tone, why = str(item["tone"]), str(item["why"]).strip()
                if tone in tones and why and _words(why) <= 30:
                    out[str(item["moment_id"])] = (tone, why)
            return out

        if not job.blocked and job.moments:
            payload = {"moments": [_moment_payload(job, m) for m in job.moments]}
            result = await self.guarded(job, "Moments", ask(self.llm, "moments", payload, parse, key=_key(job, "moments")))
            for i, m in enumerate(job.moments):  # importance stays as code set it; only tone and the reason change
                if result and m.moment_id in result:
                    tone, why = result[m.moment_id]
                    job.moments[i] = m.model_copy(update={"tone": tone, "why": why})
        await ctx.send_message(job)


class CommentatorExec(_Role):
    def __init__(self, llm: LLM):
        super().__init__("Commentator", llm)

    @handler
    async def run(self, job: ChunkJob, ctx: WorkflowContext[ChunkJob]) -> None:
        known = {m.moment_id for m in job.moments}

        def parse(answer: dict[str, Any]) -> dict[str, CanonicalLine]:
            lines = [CanonicalLine.model_validate(x) for x in answer["lines"]]
            return {ln.moment_id: ln for ln in reversed(lines) if ln.moment_id in known and "\n" not in ln.text.strip()}

        if not job.blocked and job.moments:
            payload = {
                "context": chunk_context(job.bundle, job.player, job.chunk), "previous_lines": job.previous_lines[-C.PREVIOUS_LINES:],
                "moments": [_moment_payload(job, m) for m in job.moments],
            }
            result = await self.guarded(job, "Commentator", ask(self.llm, "commentator", payload, parse, key=_key(job, "commentator")))
            job.canonical = result or {}
        await ctx.send_message(job)


class FactGuardExec(_Role):
    def __init__(self, llm: LLM):
        super().__init__("Fact Guard", llm)

    def _issues(self, job: ChunkJob, m: Moment, text: str) -> list[str]:
        # source="" so unit and location checks run against the facts alone
        return check_line(text, facts=_facts_of(job, m), bundle=job.bundle, selected=job.player, t=m.t, lang="en", source="")

    @handler
    async def run(self, job: ChunkJob, ctx: WorkflowContext[ChunkJob]) -> None:
        failing: dict[str, tuple[Moment, str, list[str]]] = {}
        for m in job.moments:
            line = job.canonical.get(m.moment_id)
            if line is None:
                job.guard[m.moment_id] = GuardResult(moment_id=m.moment_id, text="", fact_check="removed", issues=["no line was produced"])
                continue
            issues = self._issues(job, m, line.text)
            if issues:
                failing[m.moment_id] = (m, line.text, issues)
            else:
                job.guard[m.moment_id] = GuardResult(moment_id=m.moment_id, text=line.text, fact_check="pass")

        fixes: dict[str, str] = {}
        if failing and not job.blocked:
            def parse(answer: dict[str, Any]) -> dict[str, str]:
                return {str(x["moment_id"]): str(x["text"]).strip() for x in answer["fixes"]}

            payload = {"lines": [{"moment_id": mid, "line": text, "issues": issues, "facts": [_fact_payload(f) for f in _facts_of(job, m)]}
                                 for mid, (m, text, issues) in failing.items()]}
            fixes = await self.guarded(job, "Fact Guard", ask(self.llm, "fact_guard", payload, parse, key=_key(job, "fact_guard"))) or {}
        for mid, (m, before, issues) in failing.items():
            fixed = fixes.get(mid)
            if fixed and not self._issues(job, m, fixed):
                job.guard[mid] = GuardResult(moment_id=mid, text=fixed, fact_check="fixed", issues=issues, before=before, after=fixed)
            else:  # still failing (or no fix): the moment falls back to a template line
                job.guard[mid] = GuardResult(moment_id=mid, text="", fact_check="removed", issues=issues, before=before)
        await ctx.send_message(job)


class PersonalizerExec(_Role):
    def __init__(self, llm: LLM):
        super().__init__("Personalizer", llm)

    async def one_variant(self, job: ChunkJob, mode: str, lang: str) -> None:
        key = (mode, lang)
        texts: dict[str, str] = {}
        templates: set[str] = set()
        todo = [m for m in job.moments if job.guard[m.moment_id].fact_check != "removed"]

        def problems(m: Moment, text: str) -> list[str]:
            return check_line(text, facts=_facts_of(job, m), bundle=job.bundle, selected=job.player, t=m.t, lang=lang,
                              source=job.guard[m.moment_id].text)

        def parse(answer: dict[str, Any]) -> dict[str, str]:
            return {str(v.moment_id): v.text.strip() for v in (Variant(mode=mode, lang=lang, **x) for x in answer["variants"])}  # type: ignore[arg-type]

        pending = {m.moment_id: [] for m in todo}  # moment -> issues from the last try
        for attempt in range(2):  # the first try, then one retry of the failing lines with their issues
            lines = [m for m in todo if m.moment_id in pending and m.moment_id not in texts]
            if not lines or job.blocked:
                break
            payload = {"mode": mode, "lang": lang, "lines": [
                {"moment_id": m.moment_id, "text": job.guard[m.moment_id].text, "tone": m.tone, "issues": pending[m.moment_id],
                 "facts": [_fact_payload(f) for f in _facts_of(job, m)]} for m in lines]}
            result = await self.guarded(job, "Personalizer", ask(self.llm, "personalizer", payload, parse, key=_key(job, f"personalizer_{mode}_{lang}")))
            if result is None:
                break
            for m in lines:
                text = result.get(m.moment_id)
                issues = problems(m, text) if text else ["no variant was produced"]
                if text and not issues:
                    texts[m.moment_id] = text
                else:
                    pending[m.moment_id] = issues
        for m in job.moments:  # still failing (or removed upstream): the checked English line, or a template for Spanish
            if m.moment_id in texts:
                continue
            checked = job.guard[m.moment_id]
            if checked.fact_check != "removed" and lang == "en":
                texts[m.moment_id] = checked.text
            else:
                texts[m.moment_id] = template_line(m, _facts_of(job, m), job.bundle, job.player, mode, lang)
                templates.add(m.moment_id)
        job.texts[key] = {mid: strip_initials(text) for mid, text in texts.items()}
        job.is_template[key] = templates

    @handler
    async def run(self, job: ChunkJob, ctx: WorkflowContext[ChunkJob]) -> None:
        await asyncio.gather(*(self.one_variant(job, mode, lang) for mode, lang in job.variants))
        await ctx.send_message(job)


def is_big(moment: Moment) -> bool:
    """Goals, cards, penalties and any moment at BIG_IMPORTANCE get a big emotion."""
    return moment.importance >= C.BIG_IMPORTANCE or moment.trigger in C.BIG_TRIGGERS


def allowed_styles(moment: Moment, side: str, glowing: bool = False) -> tuple[tuple[str, ...], str]:
    """The emotions that fit this moment and the default among them: big moments, the last minutes, stat lines, the rest.

    ``glowing``: a goal happened within AFTERGLOW_S, so even a stat line keeps the full intensity of that goal's mood.
    """
    if is_big(moment):
        return C.BIG_STYLES[side], C.BIG_DEFAULT[side]
    if moment.trigger in ("filler", "play") and not glowing:
        return C.STAT_STYLES[side], C.STAT_DEFAULT[side]
    if moment.t >= (C.LATE_MINUTE - 1) * 60:
        return C.LATE_STYLES[side], C.LATE_DEFAULT[side]
    return C.STYLES_FOR[side], C.SIDE_DEFAULT[side]


def default_direction(moment: Moment, mode: str, lang: str, text: str, side: str = "neutral", glowing: bool = False) -> VoiceDirection:
    """Code-made speaking instructions (used when the Voice Director fails): the default emotion for the moment and side."""
    style = allowed_styles(moment, side, glowing)[1]
    return VoiceDirection(moment_id=moment.moment_id, mode=mode, lang=lang, rate="fast" if is_big(moment) else "normal", style=style)  # type: ignore[arg-type]


def fit_style(direction: VoiceDirection, moment: Moment, side: str, glowing: bool = False) -> VoiceDirection:
    """Keeps the home bias and the intensity rules: a style that does not fit (e.g. happy on a Redmond goal) is replaced."""
    allowed, fallback = allowed_styles(moment, side, glowing)
    return direction if direction.style in allowed else direction.model_copy(update={"style": fallback})


def vary_styles(directions: list[tuple[Moment, str, bool, VoiceDirection]]) -> list[VoiceDirection]:
    """In time order, changes a line whose emotion would be the same as the previous MAX_SAME_STYLE_RUN lines (big moments keep theirs)."""
    out: list[VoiceDirection] = []
    for moment, side, glowing, d in directions:
        recent = [x.style for x in out[-C.MAX_SAME_STYLE_RUN:]]
        if len(recent) == C.MAX_SAME_STYLE_RUN and all(s == d.style for s in recent) and not is_big(moment):
            other = next((s for s in allowed_styles(moment, side, glowing)[0] if s != d.style), d.style)
            d = d.model_copy(update={"style": other})
        out.append(d)
    return out


def mood_at(t: float, job: "ChunkJob") -> float:
    """The commentator's mood just before second t: positive for Azure City, negative against, fading with time (code)."""
    total = 0.0
    for m in job.plan.moments:
        age = t - m.t
        if age <= 0 or m.trigger in ("filler", "play") or age > 6 * C.MOOD_TAU_S:
            continue
        fact = job.plan.facts.get(m.fact_ids[0])
        side = home_side(fact, job.bundle) if fact else "neutral"
        if side == "neutral":
            continue
        weight = C.MOOD_GOAL_WEIGHT if m.trigger == "goal" else 1.0 if is_big(m) else m.importance
        total += (1 if side == "good" else -1) * weight * math.exp(-age / C.MOOD_TAU_S)
    return total


def mood_label(mood: float) -> str:
    """For the Voice Director: how the commentator feels coming into this line."""
    if mood >= C.MOOD_HOT:
        return "hyped (Azure City on top just now)"
    if mood >= C.MOOD_WARM:
        return "warm (good things lately for Azure City)"
    if mood <= -C.MOOD_HOT:
        return "gutted (Redmond on top just now)"
    if mood <= -C.MOOD_WARM:
        return "tense (Redmond have had the better of it lately)"
    return "settled"


def moment_side(moment: Moment, job: "ChunkJob") -> tuple[str, bool]:
    """What the moment means for Azure City, and whether the mood is hot enough to keep stat lines at full intensity.

    A stat line, a reaction or a neutral moment takes the current mood's direction when the mood is at least warm (the
    excitement carries on and fades); a real event keeps its own side, because something dramatic breaks the mood.
    """
    fact = job.facts.get(moment.fact_ids[0])
    side = home_side(fact, job.bundle) if fact else "neutral"
    mood = mood_at(moment.t, job)
    if abs(mood) >= C.MOOD_WARM and (moment.trigger in ("filler", "reaction") or side == "neutral"):
        return ("good" if mood > 0 else "bad"), abs(mood) >= C.MOOD_HOT
    return side, False


class VoiceDirectorExec(_Role):
    def __init__(self, llm: LLM):
        super().__init__("Voice Director", llm)

    async def one_variant(self, job: ChunkJob, mode: str, lang: str) -> None:
        key = (mode, lang)
        texts = job.texts[key]
        moments = {m.moment_id: m for m in job.moments}
        sided = {mid: moment_side(moments[mid], job) for mid in texts}
        sides = {mid: s for mid, (s, _) in sided.items()}
        glowing = {mid: g for mid, (_, g) in sided.items()}

        def parse(answer: dict[str, Any]) -> dict[str, VoiceDirection]:
            out = {}
            for x in answer["directions"]:
                d = VoiceDirection(mode=mode, lang=lang, **x)  # type: ignore[arg-type]
                text = texts.get(d.moment_id, "")
                words = [w.strip(".,!¡¿?").lower() for w in text.split()]
                ok_emphasis = all(w.strip(".,!¡¿?").lower() in words for w in d.emphasis)
                if text and ok_emphasis and all(0 <= p < len(words) - 1 for p in d.pauses):
                    m = moments.get(d.moment_id)
                    out[d.moment_id] = fit_style(d, m, sides[d.moment_id], glowing[d.moment_id]) if m else d
            return out

        result: dict[str, VoiceDirection] | None = None
        if not job.blocked and texts:
            payload = {"mode": mode, "lang": lang, "lines": [{"moment_id": mid, "text": t, "tone": moments[mid].tone, "importance": moments[mid].importance,
                                                         "big": is_big(moments[mid]), "for_azure_city": sides[mid],
                                                         "danger": job.bundle.danger_at(moments[mid].t),
                                                         "mood": mood_label(mood_at(moments[mid].t, job))} for mid, t in texts.items()]}
            result = await self.guarded(job, "Voice Director", ask(self.llm, "voice_director", payload, parse, key=_key(job, f"voice_{mode}_{lang}")))
        chosen = {mid: (result or {}).get(mid) or default_direction(moments[mid], mode, lang, t, sides[mid], glowing[mid]) for mid, t in texts.items()}
        ordered = sorted(texts, key=lambda mid: moments[mid].t)
        varied = vary_styles([(moments[mid], sides[mid], glowing[mid], chosen[mid]) for mid in ordered])
        job.directions[key] = dict(zip(ordered, varied))

    @handler
    async def run(self, job: ChunkJob, ctx: WorkflowContext[ChunkJob]) -> None:
        await asyncio.gather(*(self.one_variant(job, mode, lang) for mode, lang in job.variants))
        await ctx.send_message(job)


class SpeechExec(Executor):
    """Plain code, not an agent: renders every final line to an MP3 (when Speech is on and under its limits)."""

    def __init__(self, speech: SpeechClient | None, voice_for: Callable[[str, str], str]):
        super().__init__(id="Speech")
        self.speech = speech
        self.voice_for = voice_for

    @handler
    async def run(self, job: ChunkJob, ctx: WorkflowContext[ChunkJob]) -> None:
        if self.speech is not None:
            slots = asyncio.Semaphore(8)
            stopped = False

            async def one(mode: str, lang: str, mid: str, text: str) -> None:
                nonlocal stopped
                voice = self.voice_for(mode, lang)
                if stopped or not voice:
                    return
                ssml = build_ssml(text, voice, lang, job.directions[(mode, lang)][mid])
                try:
                    async with slots:
                        job.clips.setdefault((mode, lang), {})[mid] = await self.speech.synth(text, voice, ssml, key=_key(job, f"speech_{mode}_{lang}"))
                except BudgetExceeded:
                    stopped = True
                    job.notes["Speech"] = "stopped by a spend limit"
                except SpeechError as err:
                    job.notes["Speech"] = str(err)

            await asyncio.gather(*(one(mode, lang, mid, text) for (mode, lang), texts in job.texts.items() for mid, text in texts.items()))
        await ctx.send_message(job)


def _event_ids(job: ChunkJob, m: Moment) -> list[str]:
    seen: list[str] = []
    for f in _facts_of(job, m):
        for eid in f.event_ids:
            if re.fullmatch(r"e_\d+", eid) and eid not in seen:
                seen.append(eid)
    return seen


def estimate_seconds(text: str) -> float:
    """Guess for a line with no audio: about 2.7 words a second, clamped to the 2 to 5 s line length."""
    return round(min(5.0, max(2.0, _words(text) / 2.7)), 1)


def assemble_trace(job: ChunkJob, m: Moment, key: Key, line_id: str) -> Trace:
    mode, lang = key
    guard = job.guard[m.moment_id]
    facts = _facts_of(job, m)
    events = _event_ids(job, m)
    template = m.moment_id in job.is_template[key]
    clip = job.clips.get(key, {}).get(m.moment_id)
    reason = "cap" if job.blocked else "failure"
    steps: list[TraceStep] = []
    if not (job.blocked and not job.canonical):  # the model steps ran, fully or partly
        steps.append(TraceStep(agent="Interpreter", summary=job.notes.get("Interpreter") or f"{len(facts)} facts from {len(events)} events",
                               fact_ids=[f.fact_id for f in facts]))
        steps.append(TraceStep(agent="Moments", summary=job.notes.get("Moments") or f"{m.trigger}, importance {m.importance}", why=m.why or None))
        canonical = job.canonical.get(m.moment_id)
        steps.append(TraceStep(agent="Commentator", summary=job.notes.get("Commentator") or "canonical line", text=canonical.text if canonical else None))
        steps.append(TraceStep(agent="Fact Guard", fact_check=guard.fact_check, issues=guard.issues or None, before=guard.before, after=guard.after,
                               summary=job.notes.get("Fact Guard")))
    if template:
        steps.append(TraceStep(agent="Template", reason=reason, summary="Written by code from the event and rating log, no AI call",  # type: ignore[arg-type]
                               text=job.texts[key][m.moment_id], fact_check="template"))
    else:
        steps.append(TraceStep(agent="Personalizer", mode=mode, lang=lang, text=job.texts[key][m.moment_id], summary=job.notes.get("Personalizer")))  # type: ignore[arg-type]
        d = job.directions[key][m.moment_id]
        steps.append(TraceStep(agent="Voice", duration_s=clip.duration_s if clip else None, style=d.style, summary=job.notes.get("Speech") or f"rate {d.rate}"))
    return Trace(line_id=line_id, steps=steps, events=events)


class AssembleExec(Executor):
    """Builds the CommentaryChunk and a trace for every requested variant."""

    def __init__(self):
        super().__init__(id="Assemble")

    @handler
    async def run(self, job: ChunkJob, ctx: WorkflowContext[Never, ChunkResult]) -> None:
        chunks: dict[Key, CommentaryChunk] = {}
        traces: dict[str, Trace] = {}
        for key in job.variants:
            mode, lang = key
            lines = []
            for i, m in enumerate(job.moments):
                line_id = f"{job.bundle.match_id}.{job.player}.{mode}.{lang}.{job.chunk}.{i}"
                text = job.texts[key][m.moment_id]
                clip = job.clips.get(key, {}).get(m.moment_id)
                template = m.moment_id in job.is_template[key]
                guard = job.guard[m.moment_id]
                lines.append(CommentaryLine(
                    id=line_id, t=m.t, duration=clip.duration_s if clip else estimate_seconds(text), player=job.player, type=m.trigger,
                    importance=m.importance, text=text, audio_url=clip.audio_url if clip else None,
                    fact_check="template" if template else guard.fact_check if guard.fact_check != "removed" else "template"))  # type: ignore[arg-type]
                traces[line_id] = assemble_trace(job, m, key, line_id)
            chunks[key] = CommentaryChunk(match=job.bundle.match_id, player=job.player, mode=mode, lang=lang, chunk=job.chunk, lines=lines)  # type: ignore[arg-type]
        first = job.variants[0]
        final = [job.texts[first][m.moment_id] for m in job.moments]
        await ctx.yield_output(ChunkResult(chunks=chunks, traces=traces, final_lines=final, failed=job.blocked or bool(job.notes)))


def _key(job: ChunkJob, part: str) -> str:
    return f"{job.bundle.match_id}.{job.player}.{job.chunk}.{part}"


async def run_chunk(
    bundle: MatchBundle, plan: PlayerPlan, chunk: int, variants: list[Key], llm: LLM,
    speech: SpeechClient | None, voice_for: Callable[[str, str], str], previous_lines: list[str] | None = None,
) -> ChunkResult:
    """Runs the six agents (plus Speech) over one chunk and returns every requested variant with its traces."""
    moments = plan.chunk_moments(chunk)
    job = ChunkJob(bundle=bundle, plan=plan, chunk=chunk, player=plan.player_id, variants=variants, previous_lines=previous_lines or [],
                   moments=list(moments), facts={f.fact_id: f for f in plan.facts_for(moments)})
    execs = [InterpreterExec(llm), MomentsExec(llm), CommentatorExec(llm), FactGuardExec(llm), PersonalizerExec(llm),
             VoiceDirectorExec(llm), SpeechExec(speech, voice_for), AssembleExec()]
    workflow = WorkflowBuilder(start_executor=execs[0]).add_chain(execs).build()
    result = await workflow.run(job)
    return result.get_outputs()[0]
