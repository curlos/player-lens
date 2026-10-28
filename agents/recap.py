"""The full-time recap for one player, mode and language (GET /recap, shown on the full-time card).

Facts are computed here in code (goals, assists, rating, distance, off-ball credit, result); one model call words them;
Fact Guard's validator checks the text (with the recap's longer word range) and a failing text retries once with its
issues, then falls back to a code-written template. The recap is spoken with the same voice as the lines.
"""

from __future__ import annotations

from typing import NamedTuple

from agents import config as C
from agents.fact_guard import RECAP_FACT_ID, check_line
from agents.inputs import MatchBundle, build_plan
from agents.llm import LLM
from agents.models import Fact, Recap
from agents.pipeline import AgentFailed, ask
from agents.speech import SpeechClient, SpeechError, build_ssml
from app.budget import BudgetExceeded
from sim.roster import _fold  # noqa: F401  (kept next to the other name helpers)


def recap_facts(bundle: MatchBundle, player: str, plan_facts: dict[str, Fact]) -> list[Fact]:
    """The player's goals (as facts the validator knows) plus one stats fact with every number the recap may cite."""
    end = float(bundle.meta.duration_s)
    me = bundle.players[player]
    mine = [f for f in plan_facts.values() if f.kind == "goal" and (f.values.get("selected_scored") or f.values.get("selected_assisted"))]
    entries = bundle.ratings.get(player, [])
    score = bundle.meta.score
    team = bundle.team_of[player]
    mine_goals, theirs = (score.azc, score.rdm) if team == "azc" else (score.rdm, score.azc)
    result = "win" if mine_goals > theirs else "draw" if mine_goals == theirs else "defeat"
    stats = Fact(
        fact_id=RECAP_FACT_ID, t=end, kind="filler_stat", player_id=player, event_ids=["stat:recap"],
        values={
            "player": me.name, "team": bundle.team_name[team], "result": result, "score": f"{score.azc}-{score.rdm}",
            "goals": sum(1 for f in mine if f.values.get("selected_scored")), "assists": sum(1 for f in mine if f.values.get("selected_assisted")),
            "final_rating": round(entries[-1].rating_after if entries else 6.0, 1), "distance_km": round(bundle.distance_km_at(player, end), 1),
            "off_ball_credits": sum(1 for r in entries if r.off_ball and r.delta > 0),
        },
    )
    return [*mine, stats]


def template_recap(facts: list[Fact], lang: str) -> str:
    """Code-written recap, the fallback when the model is off or fails (same facts, same wording as the full-time card's own)."""
    v = facts[-1].values
    name = str(v["player"]).split(". ", 1)[-1]
    g, a, off = int(v["goals"]), int(v["assists"]), int(v["off_ball_credits"])
    if lang == "es":
        return (f"{name} termina con un {v['final_rating']}: {g} gol{'' if g == 1 else 'es'}, {a} asistencia{'' if a == 1 else 's'}, "
                f"{v['distance_km']} km recorridos y {off} acciones sin pelota premiadas.")
    return (f"{name} finishes on {v['final_rating']}: {g} goal{'' if g == 1 else 's'}, {a} assist{'' if a == 1 else 's'}, "
            f"{v['distance_km']} km covered and {off} rewarded off-ball actions.")


class RecapResult(NamedTuple):
    recap: Recap
    complete: bool  # the model wrote it and, when a voice is set up, it has its clip: only then may it be cached


async def build_recap(
    bundle: MatchBundle, data_dir, player: str, mode: str, lang: str, llm: LLM, speech: SpeechClient | None, voice: str,
) -> RecapResult:
    """The recap and whether it is complete; a template stand-in (model off or failed, a limit hit) or a missing clip is not."""
    plan = build_plan(data_dir, bundle.match_id, player)
    facts = recap_facts(bundle, player, plan.facts)
    payload = {"mode": mode, "lang": lang, "facts": [{"fact_id": f.fact_id, "kind": f.kind, "values": f.values} for f in facts]}
    key = f"{bundle.match_id}.{player}.recap_{mode}_{lang}"
    text = ""
    for _ in range(2):
        try:
            text = await ask(llm, "recap", payload, lambda a: str(a["text"]).strip(), key=key)
        except (AgentFailed, BudgetExceeded):
            text = ""
            break
        issues = check_line(text, facts=facts, bundle=bundle, selected=player, t=float(bundle.meta.duration_s), lang=lang, words=C.RECAP_WORDS)
        if not issues:
            break
        payload["issues"] = issues
        text = ""
    from_model = bool(text)
    text = text or template_recap(facts, lang)
    clip = None
    if speech is not None and voice:
        direction = None  # a recap is read at the normal pace
        try:
            clip = await speech.synth(text, voice, build_ssml(text, voice, lang, direction), key=key)
        except (SpeechError, BudgetExceeded):
            clip = None
    recap = Recap(text=text, audio_url=clip.audio_url if clip else None, duration_s=clip.duration_s if clip else None)
    voiced = speech is not None and bool(voice)
    return RecapResult(recap, from_model and (clip is not None or not voiced))
