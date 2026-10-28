"""Fact Guard's validator (specs/agents-backend.md, "Prompt rules and Fact Guard"). Pure code, no LLM.

``check_line`` returns a list of issues (empty means the line is clean). The same function checks the
Commentator's canonical line and the Personalizer's variants; pass ``source`` to also apply the variant-only
checks (units, and location or tactic words the facts do not carry). Fixing a failing line is the LLM's job
(agents/pipeline.py); the validator runs again on the fix.

What it extracts and compares against the moment's facts:
- every number (digits and spelled-out) against numbers derived from fact values;
- every player name against the facts, and every other capitalised name against the roster and blocklist
  (sim/blocklist.txt via sim.roster.is_blocked);
- action words (goal, shot, tackle, card...) against the actions the fact kinds allow (tables below, EN and
  Mexican Spanish: atajar, fuera de lugar, penal, pelota, disparo, portería, portero, regate);
- results claimed early ("the winner" before the match ended), word count, and Spanish wording rules.
All word lists are guesses to tune in this file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from agents import config as C
from agents.inputs import MatchBundle
from agents.models import Fact
from sim.roster import _fold, is_blocked, load_blocklist

# --- Action words: category -> (English regex, Mexican Spanish regex) -------------------------------------
ACTIONS: dict[str, tuple[str, str]] = {
    "goal": (r"scor(?:e|es|ed|ing)|goals?|nets?|netted|buried|buries|fires? (?:it )?home",
             r"gol(?:es|azo)?|anot\w+|defin(?:e|ió|io|ición)|(?:la|lo) (?:mete|metió|manda|clava)"),
    "shot": (r"shots?|shoots?|strikes?|effort", r"dispar\w+|remat\w+"),
    "pass": (r"pass(?:es|ed)?|sets? (?:it )?up|assists?|through ball", r"pas(?:e|es|ó)|asist\w+"),
    "tackle": (r"tackl\w+|wins? the ball|won the ball|robs?|steals?", r"entrada|barrid\w+|rob(?:a|ó|o)\w*|le quit\w+"),
    "interception": (r"intercept\w*", r"intercept\w+|corta\w*"),
    "block": (r"block(?:s|ed|ing)?", r"bloque\w+"),
    "clearance": (r"clear(?:s|ed|ance)", r"despej\w+"),
    "save": (r"sav(?:e|es|ed)|parr(?:y|ies|ied)", r"atajad\w+|ataj\w+"),
    "foul": (r"foul(?:s|ed)?|free[- ]kick|brought down", r"falta\w*|derrib\w+|tiro libre"),
    "yellow": (r"yellow|booked|booking|cautioned", r"amarilla|amonest\w+"),
    "red": (r"red card|sent off|dismissed|ordered off|sending[- ]off", r"roja|expuls\w+"),
    "penalty": (r"penalt(?:y|ies)|spot[- ]kick", r"penal(?:es|ti)?"),
    "offside": (r"offside", r"fuera de lugar"),
    "header": (r"header|heads? (?:it|the)|aerial", r"cabezazo\w*|de cabeza|a[eé]re[oa]"),
    "dribble": (r"dribbl\w+|beats? (?:his|the) man|takes? on", r"regat\w+|desborda\w*"),
    "press": (r"press(?:es|ed|ing|ure)?|harass\w*|closes? down", r"presi[oó]n\w*|presiona\w*"),
    "track_back": (r"track(?:s|ed|ing)? back|recover(?:s|ed|y)|sprints? back", r"repleg\w+|recuper\w+"),
    "mark": (r"mark(?:s|ed|ing)", r"marc(?:a|ó|aje|ando)|anul\w+"),
    "decoy": (r"decoy|drags? \w+ away|opens? (?:up )?space|dummy run", r"desmarque|abre espacio|arrastr\w+"),
    "celebrate": (r"celebrat\w+|wheels? away", r"celebr\w+"),
    "spell": (r"dominat\w+|dominance|pinned|in control|high press|end[- ]to[- ]end", r"domin\w+|presi[oó]n alta|encerrad\w+|de ida y vuelta"),
}
_ACTION_RES = {cat: (re.compile(rf"\b(?:{en})\b", re.I), re.compile(rf"\b(?:{es})\b", re.I)) for cat, (en, es) in ACTIONS.items()}

# The recap's stats fact (agents/recap.py): its action words come from what the player actually did, see _recap_cats.
RECAP_FACT_ID = "f_recap"

# Reason codes in rating facts -> the action categories they allow.
REASON_CATS = {
    "goal": {"goal", "shot", "celebrate"}, "assist": {"pass"}, "key_pass": {"pass"},
    "shot_on_target": {"shot"}, "big_chance_missed": {"shot"},
    "tackle": {"tackle"}, "interception": {"interception", "tackle"}, "block": {"block"}, "clearance": {"clearance"},
    "aerial_duel_won": {"header"}, "dribble": {"dribble"}, "beaten_by_dribble": {"dribble"}, "dispossessed": {"tackle"},
    "foul_won": {"foul"}, "foul_committed": {"foul"}, "handball": {"foul"}, "offside": {"offside", "foul"},
    "card_yellow": {"yellow", "foul"}, "card_red": {"red", "foul"},
    "gk_save": {"save"}, "gk_goal_conceded": {"goal"}, "gk_claim": {"save"}, "gk_sweep": {"clearance"},
    "error_leading_to_goal": {"goal"}, "error_leading_to_goal_earlier": {"goal"},
    "counterpress": {"press", "tackle"}, "pressure_regain": {"press", "tackle"},
    "recovery_run": {"track_back"}, "marking_denial": {"mark"}, "decoy_run": {"decoy"},
}
KIND_CATS = {
    "goal": {"goal", "shot", "celebrate"}, "shot": {"shot"}, "key_pass": {"pass"}, "tackle": {"tackle"}, "foul": {"foul"},
    "pressure_regain": {"press", "tackle"}, "counterpress": {"press", "tackle"}, "recovery_run": {"track_back"},
    "marking_denial": {"mark"}, "decoy_run": {"decoy"},
}
ACTIVITY_CATS = {"press": {"press"}, "track_back": {"track_back"}, "mark": {"mark"}, "celebrate": {"celebrate"}}

# Claims about how the match ended or a title: not allowed before full time (the facts never say so).
FUTURE_EN = re.compile(r"\b(?:winner|winning|equali[sz]er|clinch\w*|seal(?:s|ed)? (?:it|the (?:win|match|title|victory))|champions?|title|decisive|victory|final whistle)\b", re.I)
FUTURE_ES = re.compile(r"\b(?:ganador|gol del triunfo|gol de la victoria|campe\w+|t[ií]tulo|decisiv\w+|victoria|silbatazo final)\b", re.I)

# Spanish wording rules (owner decision Oct 26): Mexican football usage.
ES_WORDING = [
    (re.compile(r"\bbal[oó]n\b", re.I), "use 'pelota', not 'balón'"),
    (re.compile(r"\btiro a puerta\b", re.I), "use 'disparo a portería', not 'tiro a puerta'"),
    (re.compile(r"\bfuera de juego\b", re.I), "use 'fuera de lugar', not 'fuera de juego'"),
    (re.compile(r"\barquero\b", re.I), "use 'portero', not 'arquero'"),
]

# Wording the owner rejected by ear (Oct 27): a hyped home commentator never sounds calm.
FLAT_EN = re.compile(r"\b(?:calm(?:ly)?|quietly|steadily|comfortabl[ey])\b", re.I)
FLAT_ES = re.compile(r"\b(?:con calma|tranquil\w*|calmad\w*|sin prisa)\b", re.I)
INITIAL = re.compile(r"\b[A-ZÁÉÍÓÚÑ]\.\s?(?=[A-ZÁÉÍÓÚÑ])")  # the "G. " in "G. Lima"


def strip_initials(text: str) -> str:
    """Spoken commentary says surnames only: "G. Lima scores" becomes "Lima scores" (code, applied to every final line)."""
    return INITIAL.sub("", text)

# Score claims after a goal must match the goal's score ("azc-rdm"): levelling words only at a level score, lead words only when ahead.
LEVEL_EN = re.compile(r"\b(?:equali[sz]\w*|level(?:s|led|ling)?(?: it)?|all square|draws? level)\b", re.I)
LEVEL_ES = re.compile(r"\b(?:empat\w*|iguala\w*)\b", re.I)
LEAD_EN = re.compile(r"\b(?:ahead|leads?|in front|lead(?:ing)?)\b", re.I)
LEAD_ES = re.compile(r"\b(?:ventaja|adelante|al frente|va ganando|gana \d)\b", re.I)


def _check_score_claims(text: str, facts: list[Fact], lang: str) -> list[str]:
    goals = [f for f in facts if f.kind == "goal" and isinstance(f.values.get("score"), str)]
    if not goals:
        return []
    azc, rdm = (int(x) for x in str(goals[0].values["score"]).split("-"))
    level = LEVEL_ES if lang == "es" else LEVEL_EN
    lead = LEAD_ES if lang == "es" else LEAD_EN
    issues = []
    if azc != rdm and (m := level.search(text)):
        issues.append(f"'{m.group()}' says the score is level, but it is {azc}-{rdm}")
    if azc == rdm and (m := lead.search(text)):
        issues.append(f"'{m.group()}' claims a lead, but the score is level at {azc}-{rdm}")
    return issues


# Location and tactic words a variant may only use if the checked line or a fact already carries them.
CONCEPTS: dict[str, tuple[str, str]] = {
    "box": (r"box|penalty area", r"[aá]rea"),
    "wing": (r"wing|flank|touchline", r"banda|extremo|costado"),
    "midfield": (r"midfield\w*", r"mediocampo|medio campo|mediocampista"),
    "defence": (r"defen[cs]e|back line|defender", r"defensa|defensor|l[ií]nea defensiva"),
    "counter": (r"counter[- ]?attack|on the break", r"contraataque|contragolpe|de contra\b"),  # bare "contra" is "against" (owner's 89' header line was rejected)
    "set_piece": (r"corner|free[- ]kick|set piece", r"c[oó]rner|tiro de esquina|tiro libre|bal[oó]n parado"),
    "woodwork": (r"post|crossbar", r"poste|travesa[nñ]o|larguero"),
    "cross": (r"cross(?:es|ed)?", r"centro|centr[oó]"),
}
_CONCEPT_RES = {k: (re.compile(rf"\b(?:{en})\b", re.I), re.compile(rf"\b(?:{es})\b", re.I)) for k, (en, es) in CONCEPTS.items()}

# Spelled-out numbers (never "one", "uno", "un": too often a pronoun or article).
_NUM_WORDS_EN = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split()) if w != "one"}
_NUM_WORDS_ES = {w: i for i, w in enumerate("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciséis diecisiete dieciocho diecinueve veinte".split()) if w != "uno"}
_NUM_WORDS = {**_NUM_WORDS_EN, **{_fold(k): v for k, v in _NUM_WORDS_ES.items()}}

# Unit words after a number, and the fact value keys that carry that unit.
_UNIT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(km/h|kph|km|kil[oó]metros?|kilometres?|kilometers?|metres?|meters?|metros?|m)\b", re.I)
_XG_RE = re.compile(r"\bxg\s*(?:de|of)?\s*(\d+(?:[.,]\d+)?)", re.I)
_UNIT_KEYS = {"km": {"distance_km"}, "kmh": {"shot_speed_kmh", "speed_kmh"}, "m": {"distance_m", "deviation_m"}, "xg": {"xg"}}

TEAM_WORDS = {"azure", "city", "redmond", "united", "azc", "rdm", "atlas", "league", "liga"}
_TOKEN_RE = re.compile(r"[^\W\d_][^\W\d_'’-]*(?:['’-][^\W\d_]+)*")
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")


@lru_cache(maxsize=1)
def _blocklist() -> tuple[set[str], set[str]]:
    return load_blocklist()


def _unit_of(word: str) -> str:
    w = word.lower()
    if w in ("km/h", "kph"):
        return "kmh"
    if w.startswith("k"):
        return "km"
    return "m"


def _num_forms(value: float) -> set[str]:
    """Ways a code-computed number may be written without computing anything new (rounding only)."""
    value = abs(value)  # numbers in a line are matched unsigned ("drops 0.08" for a delta of -0.08)
    forms = {f"{value:g}", f"{round(value)}", f"{value:.1f}", f"{value:.2f}"}
    forms |= {f.rstrip("0").rstrip(".") if "." in f else f for f in set(forms)}
    if value != int(value):  # a decimal read aloud as "eight point nine": its parts are fine too
        whole, _, frac = f"{value:g}".partition(".")
        forms |= {whole, *frac}
    return forms


@dataclass
class _Context:
    """What the moment's facts allow: numbers, names, action categories, concept text."""

    numbers: set[str]
    names: set[str]  # folded roster tokens the line may mention
    cats: set[str]
    source_text: str  # facts' labels and string values, for concept checks


def _recap_cats(fact: Fact, bundle: MatchBundle, selected: str) -> set[str]:
    """Action words the recap may use: goal and pass only if the player scored or assisted, plus the off-ball actions
    behind each rewarded rating row (from its reason code, never from the credit count alone)."""
    cats: set[str] = set()
    if int(fact.values.get("goals", 0) or 0) > 0:
        cats.add("goal")
    if int(fact.values.get("assists", 0) or 0) > 0:
        cats.add("pass")
    for r in bundle.ratings.get(selected, []):
        if r.off_ball and r.delta > 0:
            cats |= REASON_CATS.get(r.reason_code, set())
    return cats


def _context(facts: list[Fact], bundle: MatchBundle, selected: str) -> _Context:
    numbers: set[str] = set()
    names: set[str] = set()
    cats: set[str] = set()
    text: list[str] = []
    roster = {p.name: p.id for p in bundle.players.values()}

    def add_player(pid: str) -> None:
        p = bundle.players[pid]
        numbers.add(str(p.number))
        names.update(_name_tokens(p.name, p.first_name))

    add_player(selected)
    for f in facts:
        if f.player_id in bundle.players:
            add_player(f.player_id)
        cats |= KIND_CATS.get(f.kind, set())
        text.append(f.label)
        for key, val in f.values.items():
            if isinstance(val, bool):
                continue
            if isinstance(val, (int, float)):
                numbers |= _num_forms(float(val))
            elif isinstance(val, str):
                text.append(val)
                numbers.update(n.replace(",", ".") for n in _NUM_RE.findall(val))
                if val in roster:
                    add_player(roster[val])
        rc = f.values.get("reason_code")
        if isinstance(rc, str):
            cats |= REASON_CATS.get(rc, set())
        if f.kind == "goal" and "assister" in f.values:
            cats.add("pass")
        if f.kind == "card":
            cats |= {"foul", "red" if f.values.get("card") == "red" else "yellow"}
        if f.kind == "foul" and f.values.get("action") == "penalty awarded":
            cats.add("penalty")
        if f.kind == "spell":
            cats.add("spell")
        if f.fact_id == RECAP_FACT_ID:
            cats |= _recap_cats(f, bundle, selected)
        act = f.values.get("activity")
        if f.kind == "filler_stat" and isinstance(act, str):
            cats |= ACTIVITY_CATS.get(act, set())
        if f.kind == "play":  # the action around the ball, plus what the selected player is doing meanwhile
            cats.add(str(f.values.get("action", "")))
            if f.values.get("event") == "free kick":
                cats.add("foul")
            cats |= ACTIVITY_CATS.get(str(f.values.get("selected_activity", "")), set())
    return _Context(numbers, names, cats, " ".join(text))


def _name_tokens(name: str, first_name: str | None) -> set[str]:
    surname = name.split(". ", 1)[-1]
    tokens = {_fold(t) for t in surname.split() if len(t) > 1}
    if first_name:
        tokens.add(_fold(first_name))
    return tokens


def roster_tokens(bundle: MatchBundle) -> dict[str, set[str]]:
    """Folded name token -> player ids, for every roster player."""
    out: dict[str, set[str]] = {}
    for p in bundle.players.values():
        for tok in _name_tokens(p.name, p.first_name):
            out.setdefault(tok, set()).add(p.id)
    return out


def _is_sentence_start(text: str, pos: int) -> bool:
    before = text[:pos].rstrip(" \"'“‘¡¿")
    return not before or before[-1] in ".!?:"


def _check_names(text: str, ctx: _Context, bundle: MatchBundle) -> list[str]:
    issues: list[str] = []
    roster = roster_tokens(bundle)
    surnames, _ = _blocklist()
    for m in _TOKEN_RE.finditer(text):
        word = re.sub(r"['’]s$", "", m.group())  # a possessive ("Redmond United's half") is the name itself
        if len(word) == 1:
            continue  # an initial such as the J in "J. Pereira"
        folded = _fold(word)
        capital = word[0].isupper() and not word.isupper()
        if capital and folded in surnames:
            issues.append(f"'{word}' is on the real-player blocklist")
        elif capital and folded in roster:
            if folded not in ctx.names:
                issues.append(f"mentions '{word}', who is not in the facts")
        elif capital and not _is_sentence_start(text, m.start()) and folded not in TEAM_WORDS and folded not in ctx.names:
            issues.append(f"'{word}' looks like a name that is not in the facts")
    return issues


def _check_numbers(text: str, ctx: _Context) -> list[str]:
    issues: list[str] = []
    found = [n.replace(",", ".") for n in _NUM_RE.findall(text)]
    for tok in _TOKEN_RE.findall(text):
        folded = _fold(tok)
        if folded in _NUM_WORDS:
            found.append(str(_NUM_WORDS[folded]))
    for n in found:
        if n not in ctx.numbers and n.lstrip("0") not in ctx.numbers:
            issues.append(f"the number {n} is not in the facts")
    return issues


def _check_actions(text: str, ctx: _Context, lang: str) -> list[str]:
    idx = 1 if lang == "es" else 0
    issues = []
    for cat, regexes in _ACTION_RES.items():
        m = regexes[idx].search(text)
        if m and cat not in ctx.cats:
            issues.append(f"'{m.group()}' claims a {cat.replace('_', ' ')} the facts do not show")
    return issues


def _check_units(text: str, facts: list[Fact]) -> list[str]:
    """Each number with a unit (km, m, km/h, xG) must match a fact value that carries that unit."""
    issues: list[str] = []
    values = [(k, v) for f in facts for k, v in f.values.items() if isinstance(v, (int, float)) and not isinstance(v, bool)]
    pairs = [(m.group(1), _unit_of(m.group(2))) for m in _UNIT_RE.finditer(text)] + [(m.group(1), "xg") for m in _XG_RE.finditer(text)]
    for num, unit in pairs:
        num = num.replace(",", ".")
        ok = any(k in _UNIT_KEYS[unit] and num in _num_forms(float(v)) for k, v in values)
        if not ok:
            issues.append(f"the unit on '{num}' ({unit}) does not match a fact")
    return issues


def _check_concepts(text: str, source: str, ctx: _Context, lang: str) -> list[str]:
    """A location or tactic word in a variant must already be in the checked line or a fact."""
    issues = []
    idx = 1 if lang == "es" else 0
    haystack = f"{source} {ctx.source_text}"
    for concept, regexes in _CONCEPT_RES.items():
        m = regexes[idx].search(text)
        if m and not regexes[0].search(haystack) and not regexes[1].search(haystack):
            issues.append(f"'{m.group()}' ({concept.replace('_', ' ')}) is not in the checked line or the facts")
    return issues


def check_line(
    text: str,
    *,
    facts: list[Fact],
    bundle: MatchBundle,
    selected: str,
    t: float,
    lang: str = "en",
    source: str | None = None,
    words: tuple[int, int] = (C.MIN_WORDS, C.MAX_WORDS),
) -> list[str]:
    """All issues with one line; empty means it passes. ``source`` is the checked line, set for variants."""
    issues: list[str] = []
    count = len([w for w in text.split() if re.search(r"\w", w)])
    if not words[0] <= count <= words[1]:
        issues.append(f"{count} words; this must be {words[0]} to {words[1]}")
    ctx = _context(facts, bundle, selected)
    issues += _check_numbers(text, ctx)
    issues += _check_names(text, ctx, bundle)
    issues += _check_actions(text, ctx, lang)
    if t < bundle.meta.duration_s - 1 and (FUTURE_ES if lang == "es" else FUTURE_EN).search(text):
        issues.append("states a result or outcome before it has happened")
    if lang == "es":
        issues += [msg for rx, msg in ES_WORDING if rx.search(text)]
    issues += _check_score_claims(text, facts, lang)
    flat = (FLAT_ES if lang == "es" else FLAT_EN).search(text)
    if flat:
        issues.append(f"'{flat.group()}' sounds flat: the commentator is a hyped home fan")
    if source is not None:
        issues += _check_units(text, facts)
        issues += _check_concepts(text, source, ctx, lang)
    return issues
