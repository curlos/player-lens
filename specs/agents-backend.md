# Spec: Agents and Backend

Oct 25, 2026 · @Carlos Martinez

## Purpose and scope

This spec defines exactly what each agent receives and returns, how the backend serves commentary, and how cost is capped. ARCHITECTURE section 5 has the roster and cadence rules; this spec is the contract Claude Code builds against, and it wins on any conflict about formats.

- Python 3.11+, FastAPI, Microsoft Agent Framework for the agent workflow, Pydantic models for every contract below (exported to `contracts/` as JSON schema).
- One Foundry-hosted small OpenAI deployment for all LLM agents, chosen by env var. Azure AI Speech for audio.
- The simulator and rating engine are not agents; they only produce the inputs.
- Never a live LLM call from tests, validation runs or simulator runs.

## Pipeline overview

The unit of work is one chunk: a 1-minute window (60 s, chunk index = min(floor(t / 60), 89), so 90 chunks per match, indices 0 to 89) of one match for one player. Match time runs 0 to `duration_s` (5400) inclusive, so the last window, chunk 89, is closed at both ends (5340 to 5400) and an event at t = 5400, such as the final whistle, belongs to it; there is no chunk 90. Each chunk runs the agents in order and produces four variants (Casual/Analyst x EN/ES).

1. **Interpreter**: events and ratings in the window become structured facts.
2. **Moments**: facts become scheduled moments under the cadence rules.
3. **Commentator**: one canonical line per moment.
4. **Fact Guard**: validates and fixes each canonical line.
5. **Personalizer**: four variants per checked line.
6. **Voice Director**: speaking instructions per variant.
7. **Speech** (plain code): audio clip and duration.

One chunk run produces the facts, moments and canonical lines once; steps 5 to 7 run per (mode, language) that is requested. Pre-generation (hero match, default star) runs all four variants for every chunk offline. On-demand runs only the requested (mode, language).

Rules for all agents:

- Each agent's output is validated against its Pydantic schema before the next agent starts. Invalid output retries once, then the moment falls back to a template line (see Caching, cap and fallback).
- Anything numeric (distances, speeds, xG, minutes, scores, ratings) is computed by code and passed in as fact fields. An LLM may repeat a number but never compute or invent one.
- Agents are stateless between chunks. The only carry-over is a `previous_lines` list (last 3 final lines of the player) passed to the Commentator to avoid repetition.

## Inputs ready from Phase 1 (match data)

Built and tested on Oct 25-26; the agent pipeline reads these and never recomputes them.

- **Match files:** `data/matches/<match_id>/{meta,events,ratings}.json` (field reference: Spec: Match Files). The backend needs only `meta`, `events` and `ratings`, never `positions`. Library: `md38_title_decider` (hero, seed 9447), `md19_blowout`, `md27_draw`, all listed in `sim/library.py`; `md38_title_decider_backup` exists but is not served in the picker.
- **Loading and validating:** Pydantic models `Meta`, `EventsFile`, `RatingsFile` in `sim/models.py` (for example `EventsFile.model_validate_json(text)`); contracts in `contracts/`. Event ids are `e_0001` upward, rating ids `r_0001` upward, player ids `azc_09`.
- **Default player:** `meta.default_player` is `azc_09` (G. Lima). Player names, numbers, slots, OVR, gender (for pronouns) and attributes are in `meta.teams[].players[]`.
- **Rating reasons:** each entry has `reason_code` and `values` (the full list of 34 codes and their values is in Spec: Frontend, "Rating log reason text"). `values` holds player ids, `xg`, `distance_m` and similar; the Interpreter copies these into fact `values`, it never computes new numbers. `off_ball: true` marks off-ball credit.
- **Linked events:** an event's optional `related` list points to its cause (a goal's shot and key pass, a pressure regain's pressure, an error's turnover and goal), so facts can cite the chain.
- **Event importance:** `importance` (0-1) is already on every event (code-computed, Spec: Rating Model); Moments uses it as is. "Involves the selected player" is a per-request boost the pipeline adds.
- **Spells:** `rating.spells.compute_spells(events)` returns 18 windows of 5 minutes: `{window, start_t, end_t, label, team, values}`. `label` is `control` (team = the side in control, the other is pinned back), `high_press` (team = the pressing side), `end_to_end` or `even`. `values` holds the numbers commentary may cite: `pass_share_azc/rdm`, `passes_*`, `pass_completion_*`, `final_third_*`, `pressures_*`, `high_pressures_*`, `shots_*`, `goals_*`, `turnovers`, `passes_per_minute`. Thresholds are in `rating/config.py`. A `spell` fact cites `spell:<window>` instead of an event id.
- **Activities** (walk, jog, press, track back...) live only in `positions.json`. If filler lines need the player's current activity, read `act` from that file once per match at startup; it is the only positions use the backend may need.
- **Commentary contracts already defined:** `CommentaryChunk`, `CommentaryLine`, `ChunkPreparing` (the 202 body) and `Trace` in `agents/models.py`, exported to `contracts/commentary_chunk.schema.json`, `commentary_preparing.schema.json` and `trace.schema.json`. The per-agent models (facts, moments, lines, Fact Guard results, variants, voice) are still to be written in `agents/models.py` and exported the same way.

## Agent contracts

All ids are strings. `t` is match seconds. Field names are final; Claude Code may add optional fields but not rename these.

**Shared input (built by code per chunk):** `match_id`, `player` (id, name, number, position), `window` (start\_t, end\_t), `events` (the match events in the window, plus the player's events from the 10 s before it), `rating_changes` (the player's rating log entries in the window), `context` (score, minute, team shape, code-computed spells per 5-minute window from `rating/spells.py`, see below), `previous_lines`.

**1. Interpreter** (light LLM)

- Output `facts[]`: `{fact_id, t, kind, player_id, event_ids[], values{}, label}`.
- `kind` is one of: goal, shot, key\_pass, tackle, foul, card, rating\_change, pressure\_regain, counterpress, recovery\_run, marking\_denial, decoy\_run, spell, filler\_stat.
- `values` holds code-computed numbers and names only (for example `xg`, `speed_kmh`, `distance_m`, `delta`, `opponent`); `rating_change` facts may also include the rating log's `reason_code`. `label` is a short neutral phrase from the LLM (max 12 words) and must contain no number or name that is not in `values`.
- Every fact must cite at least one `event_id` or `rating_log_id`, except `filler_stat` and `spell`, which cite the computed stat key instead.

**2. Moments** (light LLM plus code)

- Code builds candidates from the facts by the trigger priority in ARCHITECTURE and enforces the 5 s minimum and 15 s maximum gap. The LLM ranks candidates, assigns tone and writes the reason.
- Output `moments[]`: `{moment_id, t, trigger, importance, tone, fact_ids[], why}`.
- `tone` is one of: calm, building, excited, tense, relieved, analytical. `importance` comes from code (0 to 1); the LLM cannot change it. `why` is one sentence for the trace.

**3. Commentator** (LLM)

- Output `lines[]`: `{moment_id, text, fact_ids_used[]}`. One canonical English line per moment, 6 to 14 words, using only the moment's facts.

**4. Fact Guard** (validator plus LLM fix)

- Output per line: `{moment_id, text, fact_check, issues[], before, after}`. `fact_check` is `pass`, `fixed` or `removed`. `before` and `after` are set only when fixed.

**5. Personalizer** (LLM)

- Input: the checked line, its facts, `mode`, `lang`.
- Output `variants[]`: `{moment_id, mode, lang, text}`. Casual is plain and energetic; Analyst adds the supporting number or spell when the facts have one. Spanish is a rewrite, not a word-for-word translation.

**6. Voice Director** (light LLM)

- Output per variant: `{moment_id, mode, lang, pauses[], emphasis[], rate, style}`. `rate` is slow, normal or fast; `style` is one of the Speech voice styles allowed for the chosen voice. Code turns this into SSML.

**7. Speech** (code, not an agent)

- Output per variant: `{audio_url, duration_s}`. Audio is cached by a hash of (text, voice, ssml).

## Prompt rules and Fact Guard

**Prompts live in `agents/prompts/<agent>.md`**, one file per agent, loaded at start. Each prompt states the role, the input fields, the output schema, and the rules below. Temperature 0.2 for Interpreter, Moments and Voice Director; 0.7 for Commentator and Personalizer.

- **Commentator:** use only the listed facts. No invented players, tactics, history or weather. Never mention real players, clubs or leagues. Do not start two lines in a row the same way. Vary vocabulary across `previous_lines`. Present tense, one sentence, 6 to 14 words.
- **Personalizer:** use only facts already present in the checked line and its moment. Casual: short, warm, plain words. Analyst: may add one supporting number or spell from the facts. Spanish: natural neutral Spanish, same facts. UI-style labels are not translated; commentary is.
- **Voice Director:** pauses only at commas and sentence ends; emphasis on at most two words; faster rate for excited tone, slower for relieved or analytical.

**Fact Guard has two stages.**

1. *Validator (code).* Extract every number, player name, team name and action verb from the line. Each must map to a fact value, a known roster name or an allowed verb for that fact kind (table kept in `agents/fact_guard.py`). Also check: word count 6 to 14, no real names (blocklist), no mention of events after `t`, no result stated before it happened.
2. *Fix (LLM).* If the validator finds issues, the LLM rewrites the line using only the facts and the issue list. The validator runs again on the result.

Outcomes: first pass clean gives `pass`; fixed and re-validated gives `fixed` with `before` and `after`; still failing gives `removed` (the moment falls back to a template line, marked in the trace).

**Personalizer guard (code):** each variant runs through the same validator function the Fact Guard uses (`agents/fact_guard.py`), with the checked line and the moment's facts as the source, so it gets every Fact Guard check: numbers, player and team names, action verbs allowed for the fact kinds, no real names, no events after `t`, no result stated early (for Spanish, the verb table lists the Spanish verbs too). On top of that: (1) every unit must match the fact value's unit (m, km/h, xG), and (2) every location, tactic or relationship word (for example "box", "wing", "high press", "marking", "assist") must appear in the checked line or a fact `label`, or be in the allowed-term list for that fact kind, so the Personalizer cannot add a claim the facts do not carry (for Spanish, the term lists hold the Spanish equivalents). A failing variant retries once, then falls back to the canonical line (English) or the template (Spanish).

**Template fallback:** `agents/templates.py` holds 3 to 5 templates per fact kind, per mode and language, filled from `values`. Used whenever an LLM step fails twice, the cap is hit, or Foundry is unreachable.

## Backend endpoints

FastAPI serves the built frontend, the static match files and these routes. No auth, no sessions, no SSE. All responses are JSON unless noted.

| Route | Returns |
| --- | --- |
| `GET /health` | `{ok: true}` |
| `GET /matches` | `[{match_id, label, matchday, home, away, score, hero}]` |
| `GET /data/matches/<match_id>/{meta,events,ratings,positions}.json` | the four static files, long cache headers |
| `GET /commentary?match&player&mode&lang&chunk` | chunk object (below) |
| `GET /audio/<hash>.mp3` | audio clip, long cache headers |
| `GET /agents/trace?line=<line_id>` | trace object (below) |
| `GET /recap?match&player&mode&lang` | `{text, audio_url, duration_s}` for the full-time card |

**Chunk object:** `{match, player, mode, lang, chunk, status, lines[]}` where `status` is `ready`. Each line: `{id, t, duration, player, type, importance, text, audio_url, fact_check}`. `t` is match seconds, `type` is the moment trigger, `id` is the stable `line_id` used by the trace endpoint.

**Not ready yet:** if the chunk is not cached and generation is running, respond `202` with `{status: "preparing", retry_after: 3}`. The frontend shows "Preparing commentary" and retries; it never blocks the playback clock. If the cap is hit or generation fails, respond `200` with template lines (`fact_check: "template"`).

**Validation:** unknown match or player returns 404; mode must be `casual` or `analyst`; lang must be `en` or `es`; chunk must be an integer from 0 to 89. Invalid values return 422.

**Env vars and secrets** are read only from environment variables; none are logged or sent to the frontend. The full list is in Spec: Deployment and Environment.

## Caching, cap and fallback

- **Cache key:** (match, player, mode, lang, chunk). Stored as JSON as `<match>/<player>/<mode>_<lang>_<chunk>.json` under `data/commentary/` for the pre-generated cache and under `data/commentary_ondemand/` for the on-demand cache (two separate roots, so the baked read-only files are never mixed with runtime writes); audio under `data/audio/<hash>.mp3`.
- **Pre-generated cache** (hero match, default star, all variants, plus recaps) is built offline by `scripts/pregenerate.py` and baked into the Docker image. It is read-only at runtime.
- **On-demand cache** is written to the container disk. It is lost on restart, which is acceptable: it is regenerated under the cap.
- **Lookup order:** pre-generated, then on-demand cache, then generate (if under the cap), then template.
- **In-flight dedupe:** one lock per cache key, so ten viewers requesting the same chunk cause one generation. Others get `202` until it finishes.
- **Daily spend cap:** env var `DAILY_LLM_CAP_USD` (starts at 0, meaning no live generation). The backend counts tokens per call, converts to dollars with prices from env vars (when the cap is above 0, `LLM_PRICE_IN_PER_1M` and `LLM_PRICE_OUT_PER_1M` must both be positive; if either is missing or zero, live generation stays off and `/health` reports it, so a forgotten price can never leave spending uncapped), and keeps a daily counter (reset at UTC midnight) in a small file. At 80% of the cap, log a warning. At 100%, serve cache and templates only. A separate `DAILY_SPEECH_CAP_CHARS` guards Speech the same way; over it, lines are served as text only with `audio_url: null`.
- **Per-visitor limit:** at most 3 uncached chunk generations per IP per minute, to stop a script burning the cap.
- **Timeouts:** 20 s per LLM call, 10 s per Speech call. Failure retries once, then the template.
- **Startup check:** if a Foundry or Speech env var is missing, the app still starts and serves cache and templates; `/health` reports which services are off.
- **Logging:** log each generation (key, tokens, dollars, fact\_check outcome) to stdout; never log keys or full prompts.

## Trace data ("How this was made")

Every generated line stores a trace next to it, keyed by `line_id`. `GET /agents/trace?line=<id>` returns:

```json
{
  "line_id": "...",
  "steps": [
    {"agent": "Interpreter", "summary": "3 facts from 5 events", "fact_ids": ["f1", "f2"]},
    {"agent": "Moments", "summary": "off-ball: pressure regain, importance 0.34", "why": "..."},
    {"agent": "Commentator", "summary": "canonical line", "text": "..."},
    {"agent": "Fact Guard", "fact_check": "fixed", "issues": ["..."], "before": "...", "after": "..."},
    {"agent": "Personalizer", "mode": "analyst", "lang": "es", "text": "..."},
    {"agent": "Voice", "duration_s": 3.2, "style": "..."}
  ],
  "events": ["event ids this line is based on"]
}
```

- Template lines show a single step: `{"agent": "Template", "reason": "cap | failure"}`.
- Fact Guard is shown with an amber badge when `fact_check` is `fixed`, and the before/after diff is displayed.
- The trace also lets the frontend highlight the source events on the timeline if time allows (optional).

## Open questions

- Exact Foundry model and deployment name (decided at Azure setup); prices go in env vars so the cap math stays correct.
- Which Speech voices and styles to use for EN and ES, per mode (pick two voices after a listening test).
- Whether Moments needs an LLM at all if code can rank candidates (keep it for the trace unless it adds cost or flakiness).
- Actual cost per chunk: measure on a small batch before pre-generating the hero match.
- Recap format and length (about 60 to 90 words) to be set with the full-time card.
