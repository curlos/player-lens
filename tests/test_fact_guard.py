"""Fact Guard's validator: it catches seeded bad claims and leaves good lines alone (the 'catch rate' eval, no model involved)."""

import pytest

from agents.fact_guard import check_line
from agents.templates import template_line
from tests.conftest import MATCH, ROOT, STAR


@pytest.fixture(scope="module")
def goal_moment(plan):
    m = next(m for m in plan.moments if m.t == 5318.0)  # Lima's 89' winner
    return m, [plan.facts[f] for f in m.fact_ids]


def check(goal_moment, bundle, text, lang="en", source=None, t=5318.0):
    _, facts = goal_moment
    return check_line(text, facts=facts, bundle=bundle, selected=STAR, t=t, lang=lang, source=source)


CLEAN = [
    ("GOAL! Lima fires it home, and Azure lead 3-2!", "en"),
    ("Lima nets his second, and Thomas sets it up, 3-2!", "en"),
    ("¡GOL! Lima la manda al fondo y Azure se pone 3-2.", "es"),
    ("Lima anota con un xG de 0.13, y es 3-2 para Azure City.", "es"),
]

# (bad line, language, the kind of problem it must be flagged for)
BAD = [
    ("Lima scores again, and it is now 4-2!", "en", "number"),
    ("Lima scores, and Ribeiro looks stunned, 3-2!", "en", "not in the facts"),
    ("Lima fires home the winner, it is 3-2!", "en", "before it has happened"),
    ("Lima scores and Messi applauds from the stands!", "en", "blocklist"),
    ("Lima saves the shot brilliantly at the other end!", "en", "save"),
    ("Lima is shown a yellow card for that celebration!", "en", "yellow"),
    ("Lima fires it home, a goal worthy of the greatest strikers ever to grace this beautiful game, 3-2!", "en", "words"),
    ("Goal!", "en", "words"),
    ("Lima cleans out a header from a corner, and it is 3-2!", "en", "header"),
    ("Lima fires it home for the title, it is 3-2!", "en", "before it has happened"),
    ("¡GOL! Lima la manda al fondo del balón, es 3-2!", "es", "balón"),
    ("¡GOL! Lima define y Azure gana 3-2 en fuera de juego!", "es", "fuera de lugar"),
    ("¡GOL! Lima define con un disparo y el portero se queda sin nada, es 5-2!", "es", "number"),
    ("¡Atajada de Lima! Qué reflejos tiene el delantero, es 3-2!", "es", "save"),
]


@pytest.mark.parametrize("text,lang", CLEAN)
def test_clean_lines_pass(goal_moment, bundle, text, lang):
    assert check(goal_moment, bundle, text, lang) == []


@pytest.mark.parametrize("text,lang,kind", BAD)
def test_seeded_bad_lines_are_caught(goal_moment, bundle, text, lang, kind):
    issues = check(goal_moment, bundle, text, lang)
    assert issues, f"not caught: {text}"
    assert any(kind in i for i in issues), f"caught, but not for '{kind}': {issues}"


def test_catch_rate_is_total_and_false_positive_rate_zero(goal_moment, bundle):
    caught = sum(bool(check(goal_moment, bundle, t, l)) for t, l, _ in BAD)
    flagged_clean = sum(bool(check(goal_moment, bundle, t, l)) for t, l in CLEAN)
    assert caught == len(BAD) and flagged_clean == 0


def test_a_result_may_be_stated_at_full_time(goal_moment, bundle):
    assert check(goal_moment, bundle, "Azure City are the champions after a great win, 3-2!", t=5400.0) == []


def test_initials_are_not_unknown_names(plan, bundle):
    m = next(m for m in plan.moments if m.trigger == "card" and m.t == 3058.0)
    facts = [plan.facts[f] for f in m.fact_ids]
    assert check_line("Red card! J. Pereira of Azure City is sent off.", facts=facts, bundle=bundle, selected=STAR, t=3058.0) == []


def test_variant_checks_units_and_unsupported_concepts(goal_moment, bundle):
    ok = check(goal_moment, bundle, "Lima fires it home from an xG 0.13 chance, Azure lead 3-2.", source="Lima fires it home.")
    wrong_unit = check(goal_moment, bundle, "Lima fires it home from 0.13 km out, Azure lead 3-2.", source="Lima fires it home.")
    box = check(goal_moment, bundle, "Lima fires it home from inside the box, Azure lead 3-2.", source="Lima fires it home.")
    box_in_source = check(goal_moment, bundle, "Lima fires it home from inside the box, Azure lead 3-2.", source="Lima scores from the box.")
    assert ok == [] and any("unit" in i for i in wrong_unit) and any("box" in i for i in box) and box_in_source == []


@pytest.mark.parametrize("player", ["azc_09", "rdm_09", "azc_01"])
def test_every_template_passes_the_guard(player, bundle):
    """The fallback can never state something the facts don't: all four variants of every moment, for three players."""
    from agents.inputs import build_plan

    plan = build_plan(ROOT / "data", MATCH, player)
    for m in plan.moments:
        facts = [plan.facts[f] for f in m.fact_ids]
        for lang in ("en", "es"):
            for mode in ("casual", "analyst"):
                text = template_line(m, facts, bundle, player, mode, lang)
                assert check_line(text, facts=facts, bundle=bundle, selected=player, t=m.t, lang=lang) == [], text


def test_spanish_contra_meaning_against_is_not_a_counterattack(bundle):
    from agents.fact_guard import check_line
    from agents.models import Fact

    duel = Fact(fact_id="f_x", t=5300, kind="tackle", player_id="azc_09", event_ids=["e1"],
                values={"reason_code": "aerial_duel_won", "delta": 0.03, "rating_after": 8.3, "opponent": "L. Weber"})
    ok = check_line("¡Lima gana el duelo aéreo contra Weber!", facts=[duel], bundle=bundle, selected="azc_09", t=5300, lang="es",
                    source="Lima wins the aerial duel against Weber!")
    assert ok == []
    bad = check_line("¡Lima sale de contraataque contra Weber!", facts=[duel], bundle=bundle, selected="azc_09", t=5300, lang="es",
                     source="Lima wins the aerial duel against Weber!")
    assert any("contraataque" in i for i in bad)


def test_flat_words_are_rejected_and_initials_stripped(bundle):
    from agents.fact_guard import check_line
    from agents.models import Fact

    duel = Fact(fact_id="f_x", t=5300, kind="tackle", player_id="azc_09", event_ids=["e1"],
                values={"reason_code": "aerial_duel_won", "delta": 0.03, "rating_after": 8.3, "opponent": "L. Weber"})
    kw = dict(facts=[duel], bundle=bundle, selected="azc_09", t=5300)
    assert any("flat" in i for i in check_line("Lima wins an aerial duel against Weber calmly!", lang="en", **kw))
    assert any("flat" in i for i in check_line("¡Lima gana el duelo aéreo con calma ante Weber!", lang="es", **kw))
    from agents.fact_guard import strip_initials

    assert strip_initials("G. Lima wins it, and L. Weber is beaten!") == "Lima wins it, and Weber is beaten!"
    assert check_line("Lima wins the aerial duel against Weber! Up to 8.3!", lang="en", **kw) == []


def test_goal_lines_cannot_claim_the_wrong_score(bundle, plan):
    from agents.fact_guard import check_line

    goals = {f.values["score"]: f for f in plan.facts.values() if f.kind == "goal"}
    lead, level = goals["3-2"], goals["1-1"]
    kw = dict(bundle=bundle, selected="azc_09")
    assert any("level" in i for i in check_line("¡Gol de Lima! ¡Azure City empata el partido!", facts=[lead], t=lead.t, lang="es", **kw))
    assert any("lead" in i for i in check_line("Goal! Lima puts Azure City ahead again!", facts=[level], t=level.t, lang="en", **kw))
    assert check_line("Goal! Lima equalises for Azure City, it is 1-1!", facts=[level], t=level.t, lang="en", **kw) == []
    assert check_line("¡Gol de Lima! ¡Azure City se va adelante 3-2!", facts=[lead], t=lead.t, lang="es", **kw) == []


def test_recap_action_words_follow_what_the_player_did(bundle):
    """Lima scored and pressed, so a recap may say so; a defender with no goal may not be said to have scored."""
    from agents.inputs import build_plan
    from agents.recap import recap_facts

    lima = recap_facts(bundle, STAR, build_plan(ROOT / "data", MATCH, STAR).facts)
    assert check_line("Lima scored twice and kept pressing high all match.", facts=lima, bundle=bundle,
                      selected=STAR, t=5400.0, lang="en", words=(5, 90)) == []
    keeper = recap_facts(bundle, "rdm_01", build_plan(ROOT / "data", MATCH, "rdm_01").facts)
    assert check_line("He scored twice in a big afternoon for his side today.", facts=keeper, bundle=bundle,
                      selected="rdm_01", t=5400.0, lang="en", words=(5, 90))


def test_a_rating_loss_may_be_written_without_its_minus_sign(bundle, plan):
    lost = next(f for f in plan.facts.values() if f.values.get("reason_code") == "dispossessed" and f.values.get("delta") == -0.08)
    assert check_line("Lima loses it and his rating drops 0.08!", facts=[lost], bundle=bundle, selected=STAR, t=lost.t, lang="en") == []
