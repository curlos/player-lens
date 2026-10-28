"""Facts and the cadence schedule are code-built, deterministic and obey the commentary rules (ARCHITECTURE, "Commentary cadence")."""

from agents import config as C
from agents.inputs import _plan, build_plan, chunk_of, load_match
from tests.conftest import MATCH, ROOT, STAR


def test_plan_is_deterministic():
    a, b = build_plan(ROOT / "data", MATCH, STAR), build_plan(ROOT / "data", MATCH, "azc_06")
    again = _plan.__wrapped__(str(ROOT / "data"), MATCH, STAR)  # bypass the cache
    assert [m.model_dump() for m in a.moments] == [m.model_dump() for m in again.moments]
    assert {f.fact_id: f.model_dump() for f in a.facts.values()} == {f.fact_id: f.model_dump() for f in again.facts.values()}
    assert a.moments != b.moments  # a different player gets a different schedule


def test_every_fact_has_a_unique_id_and_cites_something(plan):
    assert len(plan.facts) == len({f.fact_id for f in plan.facts.values()})
    for f in plan.facts.values():
        assert f.event_ids, f"{f.fact_id} cites nothing"
        if f.kind not in ("spell", "filler_stat"):
            assert any(i.startswith(("e_", "r_")) for i in f.event_ids)


def test_moment_ids_are_unique_and_facts_exist(plan):
    assert len({m.moment_id for m in plan.moments}) == len(plan.moments)
    for m in plan.moments:
        assert m.fact_ids and all(fid in plan.facts for fid in m.fact_ids)


def test_silence_stays_near_the_limit(plan):
    """Quiet spells are filled after LINE_MAX_SILENCE_S; only a stoppage with nothing on the ball to call runs a little longer."""
    starts = [m.t for m in plan.moments]
    gaps = [b - a for a, b in zip(starts, starts[1:])]
    limit = C.LINE_MAX_SILENCE_S + C.LINE_EST_S
    assert sum(g <= limit for g in gaps) >= 0.9 * len(gaps), "most gaps must stay within the maximum silence plus a line"
    assert max(gaps) <= 2 * limit, "even a stoppage is not left silent for long"
    assert starts[0] <= limit


def test_minimum_gap_holds_except_for_big_moments_and_reactions(plan):
    for prev, nxt in zip(plan.moments, plan.moments[1:]):
        if nxt.importance < C.BIG_IMPORTANCE and nxt.trigger != "reaction":
            assert nxt.t - prev.t >= C.LINE_MIN_GAP_S


def test_each_goal_gets_a_line_and_a_reaction_eight_seconds_later(plan, bundle):
    goals = [e for e in bundle.events if e.type == "goal"]
    assert len(goals) == 5
    by_t = {m.t: m for m in plan.moments}
    for g in goals:
        assert by_t[g.t].trigger == "goal"
        assert by_t[min(g.t + C.REACTION_DELAY_S, bundle.meta.duration_s)].trigger == "reaction"


def test_stars_own_goal_is_the_biggest_moment_and_numbers_come_from_the_events(plan, bundle):
    lima_goals = [f for f in plan.facts.values() if f.kind == "goal" and f.values["selected_scored"]]
    assert [f.values["minute"] for f in lima_goals] == [39, 89]
    winner = lima_goals[-1]
    event = bundle.event_by_id[winner.event_ids[0]]
    assert winner.values["score"] == f"{event.score.azc}-{event.score.rdm}" == "3-2"
    assert winner.values["goals_so_far"] == 2 and winner.values["xg"] == round(event.xg, 2)
    moment = next(m for m in plan.moments if winner.fact_id in m.fact_ids and m.trigger == "goal")
    assert moment.importance == 1.0 and moment.tone == "excited"


def test_chunks_partition_the_moments(plan):
    seen = []
    for c in range(C.MAX_CHUNK + 1):
        for m in plan.chunk_moments(c):
            assert chunk_of(m.t) == c
            seen.append(m.moment_id)
    assert sorted(seen) == sorted(m.moment_id for m in plan.moments)
    assert chunk_of(5400) == 89 and chunk_of(59.9) == 0 and chunk_of(60) == 1


def test_a_second_yellow_is_merged_into_its_red(bundle):
    plan = build_plan(ROOT / "data", MATCH, "azc_06")  # J. Pereira's second yellow then red at 3058 s
    cards = [f for f in plan.facts.values() if f.kind == "card" and f.values["player"] == bundle.name("azc_06")]
    assert [c.values["card"] for c in cards if c.t == 3058.0] == ["red"]


def test_unknown_player_is_rejected():
    import pytest

    with pytest.raises(KeyError):
        build_plan(ROOT / "data", MATCH, "xxx_99")


def test_match_loads_all_three_library_matches():
    for match in ("md38_title_decider", "md19_blowout", "md27_draw"):
        assert len(load_match(ROOT / "data", match).players) == 22


def test_quiet_spells_describe_the_play_and_stat_lines_stay_rare(bundle, plan):
    stats = [m.t for m in plan.moments if m.trigger == "filler"]
    assert all(b - a >= C.STAT_EVERY_S for a, b in zip(stats, stats[1:])), "two stat lines closer than STAT_EVERY_S"
    plays = [m for m in plan.moments if m.trigger == "play"]
    assert len(plays) > len(stats), "quiet spells should mostly be about the game around the ball"
    for m in plays:
        fact = plan.facts[m.fact_ids[0]]
        event = bundle.event_by_id[fact.event_ids[0]]  # every play line cites a real event near its second
        assert fact.kind == "play" and m.t - C.PLAY_WINDOW_S[0] <= event.t <= m.t + C.PLAY_WINDOW_S[1]
        assert fact.values["actor"] == bundle.name(event.player) and fact.values["action"] == C.PLAY_ACTIONS[event.type]


def test_every_visible_rating_change_is_commented_for_every_player(bundle):
    """Owner, Oct 27: any non-zero rating-log row (the rows the frontend log shows), positive or negative, gets a line."""
    for player in bundle.players:
        plan = build_plan(ROOT / "data", MATCH, player)
        cited = {i for m in plan.moments for fid in m.fact_ids for i in plan.facts[fid].event_ids}
        for r in bundle.ratings.get(player, []):
            if r.delta != 0:
                assert r.id in cited, f"{player} {r.reason_code} {r.delta} at {r.t} is never commented"


def test_a_negative_rating_change_is_never_praised_by_the_templates(bundle):
    from agents.templates import template_line

    plan = build_plan(ROOT / "data", MATCH, STAR)
    negative = [m for m in plan.moments if plan.facts[m.fact_ids[0]].values.get("delta", 0) < 0]
    assert negative, "Lima has negative rating moments (dispossessed, a foul)"
    for m in negative:
        facts = [plan.facts[f] for f in m.fact_ids]
        for mode in ("casual", "analyst"):
            assert not any(p in template_line(m, facts, bundle, STAR, mode, "en") for p in ("Nice bit of work", "benefits", "taking the rating"))
            assert not any(p in template_line(m, facts, bundle, STAR, mode, "es") for p in ("Buen trabajo", "agradece", "sube"))


def test_no_moment_is_scheduled_after_full_time(bundle):
    for player in bundle.players:
        plan = build_plan(ROOT / "data", MATCH, player)
        assert all(m.t <= bundle.meta.duration_s for m in plan.moments), player
