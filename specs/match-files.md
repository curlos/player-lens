# Spec: Match Files

Oct 25, 2026 · @Carlos Martinez

## Purpose and general rules

The simulator writes four JSON files per match into `data/matches/<match_id>/`. This spec fixes their field names. The Pydantic models in `sim/models.py` implement it and export JSON schema to `contracts/`; the frontend types are generated from those schemas. Field names here are final.

- **Time** `t` is match seconds from kickoff, a number with at most one decimal. The match has no halftime and no side switch.
- **Space** is meters, origin top-left, x 0 to 105, y 0 to 68. Azure City attacks left to right. In `positions.json` only, values are integer decimeters.
- **Ids** are lowercase strings. Players: team abbreviation plus shirt number, for example `azc_09`, `rdm_10`. Events: `e_0001` upward in time order. Rating entries: `r_0001` upward. The ball is `ball`, the referee is `ref`.
- **Teams** are `azc` (Azure City) and `rdm` (Redmond United) everywhere.
- Every file includes `match_id` and `schema_version` (start at 1).
- Unknown extra fields are ignored by readers; required fields are never renamed or removed without bumping the version.

## meta.json

Small (a few KB). Everything the UI needs before playback.

| Field | Type | Meaning |
| --- | --- | --- |
| `match_id` | string | for example `md38_title_decider` |
| `label`, `matchday` | string, int | shown in the match picker; optional blurb (short string such as "Title decider") sits beside them |
| `seed` | int | simulator seed |
| `hero` | bool | true for the pre-generated hero match |
| `title_decider` | bool | enables the champions line on the full-time card |
| `duration_s` | int | match length in seconds; always 5400 (exactly 90:00, no stoppage time) |
| `score` | `{azc, rdm}` | final score |
| `default_player` | string | player id selected on load |
| `teams` | array of 2 | team objects below |
| `activities` | string\[\] | lookup list for the activity codes in `positions.json` |
| `entity_order` | string\[\] | order of the 24 entities in `positions.json` |

**Team object:** `id`, `name`, `abbr`, `formation`, `color`, `keeper_color`, `players[]`.

**Player object:** `id`, `name`, `number`, `position`, `slot`, `ovr`, `gender`, `temperament`, `attributes{}` (the full attribute set, since the Analyst commentary may cite them).

```json
{
  "match_id": "md38_title_decider", "schema_version": 1, "label": "Matchday 38", "blurb": "Title decider", "matchday": 38,
  "seed": 40117, "hero": true, "title_decider": true, "duration_s": 5400,
  "score": {"azc": 3, "rdm": 2}, "default_player": "azc_09",
  "teams": [{"id": "azc", "name": "Azure City", "abbr": "AZC", "formation": "4-3-3",
    "color": "#3B82F6", "keeper_color": "#E6F23A",
    "players": [{"id": "azc_09", "name": "R. Valdemar", "number": 9, "position": "ST", "slot": "ST",
      "ovr": 91, "gender": "male", "temperament": "normal", "attributes": {"finishing": 94}}]}],
  "activities": ["stand", "walk", "jog", "run", "sprint"],
  "entity_order": ["azc_01", "azc_02", "rdm_11", "ref", "ball"]
}
```

The example is shortened; real files list all 11 players per team and all 24 entities.

## events.json

A JSON array of events in time order (about 1,500 to 2,000), wrapped as `{match_id, schema_version, events[]}`.

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | `e_0412`, unique |
| `t` | number | match seconds |
| `type` | string | one of the codes below |
| `team` | `azc` or `rdm` | team performing the event |
| `player` | string | main player id (the passer, shooter, tackler, fouler) |
| `other` | string, optional | second player (receiver, opponent, fouled player) |
| `from`, `to` | `{x, y}`, optional | meters; for ball actions the start and end point |
| `outcome` | string | `success`, `fail`, `goal`, `saved`, `blocked`, `off_target`, `post`, `awarded` or `none` |
| `xg` | number, optional | shots only, 0 to 1 |
| `speed_kmh` | number, optional | shots only |
| `importance` | number | 0 to 1, computed by code (used by crowd audio and commentary) |
| `score` | `{azc, rdm}` | score right after this event |

**Event types that can change a rating:** pass, key\_pass, shot, goal, save, tackle, interception, block, clearance, aerial\_duel, dribble, foul, handball, offside, card\_yellow, card\_red, pressure, pressure\_regain, counterpress, recovery\_run, marking\_denial, decoy\_run, shape\_check, error\_leading\_to\_goal, big\_chance\_missed, injury, gk\_claim, gk\_sweep.

Goalkeeper actions: `save` is a stopped shot on target; `gk_claim` is a catch or punch of a cross or high ball (`player` is the keeper); `gk_sweep` is the keeper leaving his line to clear or collect a ball played behind the defense. "GK goal conceded" has no event of its own: the keeper's rating entry points to the `shot` or `goal` event that beat him, with `reason_code` `gk_goal_conceded`.

**Restarts:** kickoff, throw\_in, goal\_kick, corner, free\_kick, penalty.

`foul` is the one code for a foul (not `foul_committed`); `player` is the offender and `other` the player fouled. Activities (stand, run, and so on) are not events; they live in `positions.json`.

```json
{ "id": "e_0412", "t": 1834.0, "type": "shot", "team": "azc", "player": "azc_09",
  "from": {"x": 91.2, "y": 30.5}, "to": {"x": 105.0, "y": 33.1},
  "outcome": "goal", "xg": 0.31, "speed_kmh": 112, "importance": 0.95,
  "score": {"azc": 1, "rdm": 0} }
```

## ratings.json

The rating log: `{match_id, schema_version, start: 6.0, entries[]}`, entries in time order. A player's rating at time t is `start` plus the sum of their `delta` values with `t` at or before it.

| Field | Type | Meaning |
| --- | --- | --- |
| `id` | string | `r_0087`, unique |
| `t` | number | match seconds |
| `player` | string | player id |
| `event_id` | string | the event in `events.json` that caused it; always an event, including off-ball credit (pressure regain, counterpress, recovery run, marking denial, decoy run and shape check are all event types). Spells (control vs chaos patterns) are commentary facts only and never cause a rating change |
| `raw_delta` | number | signed, the table value after repeat decay but before the soft cap (see Spec: Rating Model) |
| `scale` | number | the soft-cap scale factor applied, 0 to 1 |
| `delta` | number | signed, two decimals, the final change: `raw_delta` x `scale` |
| `rating_after` | number | player's rating right after this entry (convenience; must equal 6.0 plus the sum) |
| `reason_code` | string | stable code, for example `pressure_regain`, `key_pass`, `goal` |
| `values` | object | numbers and names the reason text needs (for example `{"opponent": "rdm_06", "distance_m": 22}`) |
| `off_ball` | bool | true for credit given away from the ball |

Reason text ("Won the ball back after pressing") is not stored. The frontend builds it from `reason_code` and `values` using EN and ES templates, so the log is localized without any LLM call. Rating deltas are not edited after the file is written.

```json
{ "id": "r_0087", "t": 1790.0, "player": "azc_09", "event_id": "e_0401", "raw_delta": 0.12, "scale": 0.94, "delta": 0.11,
  "rating_after": 7.30, "reason_code": "pressure_regain",
  "values": {"opponent": "rdm_06", "distance_m": 22}, "off_ball": true }
```

## positions.json

The biggest file, kept compact: one record per entity, one sample per second.

```json
{ "match_id": "md38_title_decider", "schema_version": 1, "hz": 1, "unit": "dm", "seconds": 5401,
  "entities": [
    { "id": "azc_01", "xy": [525, 340, 527, 338], "act": [0, 1] },
    { "id": "ball",   "xy": [525, 340, 560, 330] }
  ] }
```

- `entities` has 24 records in the order given by `meta.entity_order`.
- `xy` is a flat integer array: index 2i is x and 2i+1 is y at second i, in decimeters (610, 300 means x 61.0 m, y 30.0 m). Length is 2 x `seconds`.
- `act` (players and referee only) has one small integer per second: an index into `meta.activities`. It is used for labels like "Celebrating" and for tests; it is never rated.
- `seconds` is `floor(duration_s) + 1`, so a sample exists for the final second.
- The ball carries no `act`. When the ball is out of play for a restart it stays at the restart spot.
- Frontend: read `floor(t)` and `ceil(t)`, interpolate linearly. Parse once into `Int16Array`s.

## Validation and open questions

The simulator's final step runs these checks before writing; any failure aborts the run:

- Event ids unique and time-ordered; `t` between 0 and `duration_s`.
- Every `player`, `other` and `event_id` reference exists; every rating entry points to a real event.
- For each player, `rating_after` equals 6.0 plus the running sum of deltas, within 0.01; each entry's `delta` equals `raw_delta` x `scale` within 0.01.
- Final event score equals `meta.score`; the number of `goal` events equals the total score.
- `positions.json` has 24 entities, correct array lengths, every point inside the pitch (a small margin for the ball), no player faster than max speed between seconds.
- Re-running with the same seed gives byte-identical files.

**Open questions**

- Decided: the server compresses responses on the fly; no gzip files on disk.
- `Deferred: the EN and ES reason templates per reason_code are written during the frontend build (Claude Code drafts them, the owner checks them)`.
- `Decided: meta has an optional blurb, shown in the match picker`.
