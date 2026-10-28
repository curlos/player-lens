"""The six-agent workflow with a fake model and fake Speech: handoffs, Fact Guard fixes, retries, fallbacks and traces."""

import asyncio

import pytest

from agents.inputs import build_plan
from agents.pipeline import ChunkResult, run_chunk
from agents.service import OffLLM
from tests.conftest import MATCH, ROOT, STAR
from tests.fakes import FakeLLM, FakeSpeech

BAD = "Lima fires home the winner from the edge of the box, 3-2!"
BOTH = [("casual", "en"), ("analyst", "es")]


def run(bundle, plan, llm, variants=BOTH, speech=None, chunk=88, previous=None) -> ChunkResult:
    voice = lambda mode, lang: f"voice-{lang}-{mode}"  # noqa: E731
    return asyncio.run(run_chunk(bundle, plan, chunk, variants, llm, speech, voice, previous))


def goal_line(result, key=("casual", "en")):
    return next(ln for ln in result.chunks[key].lines if ln.type == "goal")


def test_agents_run_in_order_and_every_variant_is_produced(bundle, plan):
    llm, speech = FakeLLM(), FakeSpeech()
    result = run(bundle, plan, llm, speech=speech)
    order = []
    for name in llm.calls:
        if name not in order:
            order.append(name)
    # Fact Guard's model fixer only runs when the code validator found something, so it is absent for clean lines
    assert order == ["interpreter", "moments", "commentator", "personalizer", "voice_director"] and "fact_guard" not in llm.calls
    assert llm.calls.count("personalizer") == 2 and llm.calls.count("voice_director") == 2  # one per requested variant
    assert set(result.chunks) == set(BOTH)
    for chunk in result.chunks.values():
        assert [ln.t for ln in chunk.lines] == sorted(ln.t for ln in chunk.lines)
        assert all(ln.audio_url and ln.duration > 0 for ln in chunk.lines)
    assert len(speech.said) == 2 * len(plan.chunk_moments(88))


def test_fact_guard_fixes_an_unsupported_line_and_the_trace_shows_it(bundle, plan):
    result = run(bundle, plan, FakeLLM(bad_line=BAD), speech=FakeSpeech())
    line = goal_line(result)
    assert line.fact_check == "fixed" and "winner" not in line.text and "3-2" in line.text
    steps = {s.agent: s for s in result.traces[line.id].steps}
    assert list(steps) == ["Interpreter", "Moments", "Commentator", "Fact Guard", "Personalizer", "Voice"]
    guard = steps["Fact Guard"]
    assert guard.fact_check == "fixed" and guard.before == BAD and guard.after == line.text and len(guard.issues) >= 2
    assert steps["Commentator"].text == BAD and steps["Personalizer"].mode == "casual" and steps["Voice"].duration_s


def test_unfixable_line_is_removed_and_becomes_a_template(bundle, plan):
    result = run(bundle, plan, FakeLLM(bad_line=BAD, fix_text="Lima fires home the winner, it is {score}!"))
    line = goal_line(result)
    assert line.fact_check == "template" and "winner" not in line.text
    steps = {s.agent: s for s in result.traces[line.id].steps}
    assert steps["Fact Guard"].fact_check == "removed" and steps["Template"].reason == "failure"


def test_a_failing_agent_is_retried_once_then_the_chunk_still_comes_out(bundle, plan):
    flaky = FakeLLM(flaky=("commentator",))
    result = run(bundle, plan, flaky)
    assert flaky.calls.count("commentator") == 2  # one failure, one retry that worked
    assert all(ln.fact_check == "pass" for ln in result.chunks[("casual", "en")].lines)

    down = FakeLLM(fail=("commentator",))
    result = run(bundle, plan, down)
    assert down.calls.count("commentator") == 2  # retried once, then gave up
    assert all(ln.fact_check == "template" for ln in result.chunks[("casual", "en")].lines)
    assert goal_line(result).text.startswith("GOAL!")  # a fact-checked template, never blank


def test_roles_fall_back_without_stopping_the_chunk(bundle, plan):
    result = run(bundle, plan, FakeLLM(fail=("interpreter", "moments", "voice_director")))
    chunk = result.chunks[("casual", "en")]
    assert all(ln.fact_check == "pass" for ln in chunk.lines)
    steps = {s.agent: s for s in result.traces[chunk.lines[0].id].steps}
    assert "failed twice" in steps["Interpreter"].summary and "failed twice" in steps["Moments"].summary


def test_personalizer_failure_falls_back_to_checked_english_or_a_spanish_template(bundle, plan):
    result = run(bundle, plan, FakeLLM(bad_line=BAD, fail=("personalizer",)))
    english, spanish = result.chunks[("casual", "en")], result.chunks[("analyst", "es")]
    assert all(ln.fact_check in ("pass", "fixed") for ln in english.lines)  # the checked English line
    assert all(ln.fact_check == "template" for ln in spanish.lines)  # Spanish never falls back to English
    assert goal_line(result, ("analyst", "es")).text == "Lima define una ocasión de xG 0.13. Es 3-2."  # Mexican Spanish, numbers from the facts


def test_a_spend_limit_gives_template_lines_marked_cap_and_no_audio(bundle, plan):
    speech = FakeSpeech()
    result = run(bundle, plan, OffLLM(), speech=None)
    for chunk in result.chunks.values():
        assert all(ln.fact_check == "template" and ln.audio_url is None for ln in chunk.lines)
    steps = result.traces[goal_line(result).id].steps
    assert [s.agent for s in steps] == ["Template"] and steps[0].reason == "cap"
    assert speech.said == []


def test_the_model_cannot_change_importance_or_invent_moments(bundle, plan):
    result = run(bundle, plan, FakeLLM())
    expected = {m.t: m.importance for m in plan.chunk_moments(88)}
    assert {ln.t: ln.importance for ln in result.chunks[("casual", "en")].lines} == expected


def test_labels_with_numbers_or_names_are_dropped(bundle, plan):
    class BadLabels(FakeLLM):
        async def complete(self, agent, payload, *, key):
            if agent == "interpreter":
                return {"labels": {f["fact_id"]: ("Lima scores a hat-trick in 3 minutes" if i == 0 else "a fine plain label") for i, f in enumerate(payload["facts"])}}
            return await super().complete(agent, payload, key=key)

    llm = BadLabels()
    run(bundle, plan, llm)
    sent = llm.payloads["commentator"]["moments"]
    labels = [f["label"] for m in sent for f in m["facts"]]
    assert "" in labels and "a fine plain label" in labels and not any("Lima" in x or "3" in x for x in labels)


def test_commentator_gets_previous_lines_and_moment_facts(bundle, plan):
    llm = FakeLLM()
    run(bundle, plan, llm, previous=["Earlier line one.", "Earlier line two."])
    payload = llm.payloads["commentator"]
    assert payload["previous_lines"] == ["Earlier line one.", "Earlier line two."]
    goal = next(m for m in payload["moments"] if m["trigger"] == "goal")
    assert goal["facts"][0]["values"]["score"] == "3-2"  # numbers come from code, never from the model


def test_final_lines_feed_the_next_chunk(bundle, plan):
    result = run(bundle, plan, FakeLLM(), variants=[("casual", "en")])
    assert result.final_lines == [ln.text for ln in result.chunks[("casual", "en")].lines]


@pytest.mark.parametrize("player", ["azc_06", "rdm_10"])
def test_works_for_other_players_and_chunks(bundle, player):
    other = build_plan(ROOT / "data", MATCH, player)
    for chunk in (0, 51, 89):
        result = run(bundle, other, FakeLLM(), variants=[("analyst", "en")], chunk=chunk)
        assert [ln.t for ln in result.chunks[("analyst", "en")].lines] == [m.t for m in other.chunk_moments(chunk)]


def test_default_direction_is_never_flat_for_a_big_moment():
    from agents import config as C
    from agents.models import Moment
    from agents.pipeline import default_direction

    goal = Moment(moment_id="m1", t=10, trigger="goal", importance=0.95, tone="calm", fact_ids=["f1"])
    filler = Moment(moment_id="m2", t=20, trigger="filler", importance=0.1, tone="calm", fact_ids=["f1"])
    assert default_direction(goal, "casual", "en", "Goal!", "good").style in C.BIG_STYLES["good"]
    assert default_direction(goal, "casual", "en", "Goal!", "bad").style in C.BIG_STYLES["bad"]
    assert default_direction(filler, "casual", "en", "He runs.").style in C.VOICE_STYLES


def test_home_commentators_never_celebrate_a_redmond_goal():
    from agents.models import Moment, VoiceDirection
    from agents.pipeline import fit_style

    goal = Moment(moment_id="m1", t=10, trigger="goal", importance=0.95, tone="excited", fact_ids=["f1"])
    happy = VoiceDirection(moment_id="m1", mode="casual", lang="en", style="ecstatic")
    assert fit_style(happy, goal, "bad").style == "defeated"
    assert fit_style(happy, goal, "good").style == "ecstatic"
    small = Moment(moment_id="m2", t=10, trigger="off_ball", importance=0.3, tone="calm", fact_ids=["f1"])
    assert fit_style(VoiceDirection(moment_id="m2", mode="casual", lang="en", style="defeated"), small, "good").style == "excited"


def test_home_side_follows_azure_city(bundle, plan):
    from agents.inputs import home_side

    goals = [f for f in plan.facts.values() if f.kind == "goal"]
    assert {home_side(f, bundle) for f in goals} == {"good", "bad"}  # the hero match has goals for both sides
    assert all(home_side(f, bundle) == ("good" if f.values["team"] == "Azure City" else "bad") for f in goals)
    cards = [f for f in plan.facts.values() if f.kind == "card"]
    assert all(home_side(f, bundle) == ("bad" if f.values["team"] == "Azure City" else "good") for f in cards)
    for f in (f for f in plan.facts.values() if f.kind == "filler_stat"):  # stat lines follow the score
        azc, rdm = map(int, f.values["score"].split("-"))
        assert home_side(f, bundle) == ("good" if azc > rdm else "bad" if azc < rdm else "neutral")


def test_cards_are_big_and_danger_comes_from_the_ball(bundle):
    from agents.models import Moment
    from agents.pipeline import is_big

    card = Moment(moment_id="m", t=10, trigger="card", importance=0.4, tone="tense", fact_ids=["f1"])
    assert is_big(card)
    dangers = {bundle.danger_at(t) for t in range(0, 5400, 7)}
    assert dangers == {"azure_attacking", "redmond_attacking", "none"}
    assert all((bundle.danger_at(t) == "azure_attacking") == (bundle.ball_x_at(t) >= 80) for t in range(0, 5400, 97))


def test_emotion_rules_stat_lines_late_moments_and_no_long_repeats():
    from agents import config as C
    from agents.models import Moment, VoiceDirection
    from agents.pipeline import fit_style, vary_styles

    def d(style, mid="m"):
        return VoiceDirection(moment_id=mid, mode="casual", lang="en", style=style)

    stat = Moment(moment_id="s", t=1200, trigger="filler", importance=0.1, tone="calm", fact_ids=["f"])
    assert fit_style(d("frustrated"), stat, "bad").style in C.STAT_STYLES["bad"]  # no frustration over a jog
    header = Moment(moment_id="h", t=5300, trigger="key_event", importance=0.5, tone="calm", fact_ids=["f"])
    assert fit_style(d("confident"), header, "good").style in C.LATE_STYLES["good"]  # 89': hyped
    run = vary_styles([(stat, "bad", False, d("anxious", f"m{i}")) for i in range(4)])
    assert [x.style for x in run][:2] == ["anxious", "anxious"] and run[2].style != "anxious"
    for side in ("good", "bad", "neutral"):  # never a flat emotion as a fallback
        assert {C.STAT_DEFAULT[side], C.SIDE_DEFAULT[side], C.LATE_DEFAULT[side]}.isdisjoint({"calm", "confident", "default"})


def test_the_mood_carries_after_a_goal_and_fades(bundle, plan):
    from agents import config as C
    from agents.models import Moment
    from agents.pipeline import ChunkJob, mood_at, moment_side

    goal = next(f for f in plan.facts.values() if f.kind == "goal" and f.values["team"] == "Azure City")
    stat = next(f for f in plan.facts.values() if f.kind == "filler_stat")
    job = ChunkJob(bundle=bundle, plan=plan, chunk=0, player="azc_09", variants=[], previous_lines=[], facts={stat.fact_id: stat})
    soon = Moment(moment_id="a", t=goal.t + 20, trigger="filler", importance=0.1, tone="calm", fact_ids=[stat.fact_id])
    assert moment_side(soon, job) == ("good", True)  # hyped right after the goal, whatever the score says
    assert mood_at(goal.t + 20, job) > mood_at(goal.t + 120, job) > mood_at(goal.t + 400, job)  # it fades
    calm = [t for t in range(600, 5400, 30) if abs(mood_at(t, job)) < C.MOOD_WARM]
    assert calm, "the mood must settle somewhere in the match"
