"""The match library: three fixed seeds, all Azure City vs Redmond United (PRODUCT, "Match library").

Seeds were found by scripts/find_seeds.py against the committed data/world.json and the current
simulator config. Changing either changes every match, so re-run the search after any change.
"""

from sim.pipeline import MatchInfo

LIBRARY: list[MatchInfo] = [
    # Hero (owner pick, Oct 26): 2-2 after RDM's 88' equaliser, then the star's 89' title winner.
    MatchInfo(match_id="md38_title_decider", seed=9447, label="Matchday 38", matchday=38, blurb="Title decider",
              hero=True, title_decider=True),
    MatchInfo(match_id="md19_blowout", seed=3269, label="Matchday 19", matchday=19, blurb="Statement win"),
    MatchInfo(match_id="md27_draw", seed=115, label="Matchday 27", matchday=27, blurb="Honours even"),
]

# Built and validated like the library, but not listed in the match picker.
BACKUPS: list[MatchInfo] = [
    # The first hero (3-2, star scores twice, 83' penalty winner); kept in case the new one has issues.
    MatchInfo(match_id="md38_title_decider_backup", seed=2378, label="Matchday 38", matchday=38,
              blurb="Title decider (backup)", title_decider=True),
]
