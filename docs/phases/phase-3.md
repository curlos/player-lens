# Phase 3 handoff: AI Commentary (done Oct 27, 2026; Lima's hero commentary fully pre-generated)

> Short orientation notes for the next phase's session: what exists, where, and what not to break. This is a summary, not a substitute: still read CLAUDE.md, PRODUCT.md, ARCHITECTURE.md, TASKS.md, `docs/decisions.md`, the specs your phase prompt lists, `docs/phases/phase-1.md`, `docs/phases/phase-2.md` and the `docs/ui/` images. The specs win over this file.

## What was built

| Piece | Where |
| --- | --- |
| Per-agent contracts (`Fact`, `Moment`, `CanonicalLine`, `GuardResult`, `Variant`, `VoiceDirection`, `Recap`), exported to `contracts/`, TS types regenerated | `agents/models.py`, `scripts/export_schemas.py`, `web/src/types/generated/` |
| Code-built inputs: match loading, facts with computed numbers, the cadence schedule, chunk slicing, the "home side", ball danger and mood helpers | `agents/inputs.py`, knobs in `agents/config.py` |
| The six-agent workflow on Microsoft Agent Framework (one `Agent` per role, one `Executor` per step, chained with `WorkflowBuilder`) and the emotion rules in code (`is_big`, `allowed_styles`, `fit_style`, `vary_styles`, `mood_at`) | `agents/pipeline.py`, prompts in `agents/prompts/*.md` |
| Fact Guard validator (pure code) and the template fallback (separate frames for a rating change that went down) | `agents/fact_guard.py`, `agents/templates.py` |
| Model client (Foundry, v1 endpoint), Speech (REST, SSML with `express-as` styles, clip cache), full-time recap | `agents/llm.py`, `agents/speech.py`, `agents/recap.py` |
| Chunk service with every fallback | `agents/service.py` |
| FastAPI app: `/health`, `/matches`, `/data/matches/...`, `/commentary` (200 or 202), `/audio/<hash>.mp3`, `/agents/trace`, `/recap`; the only reader of env vars; plain-file store; spend ledger and the all-time live cap | `app/main.py`, `app/settings.py`, `app/cache.py`, `app/budget.py` |
| Offline pre-generation (hero match, `azc_09` only), the spend report, a one-call smoke test | `scripts/pregenerate.py`, `scripts/spend.py`, `scripts/smoke_test.py` |
| Frontend: commentary and trace on HTTP (202 handled, goal lines re-timed with `shownAt`, offline template fallback kept), recap, voice playback with a line queue, danger-following volume and a limiter, the full trace view | `web/src/lib/commentary.ts`, `web/src/lib/audio.ts`, `web/src/lib/crowd.ts`, `web/src/lib/config.ts`, `web/src/components/AgentTrace.tsx`, `CommentaryPanel.tsx`, `FullTimeCard.tsx`, `web/vite.config.ts` |
| Tests: 178 Python and 49 Vitest at the end of the phase (180 Python after Phase 4's cost-proof tests). None calls Azure. | `tests/`, `web/src/lib/*.test.ts` |

## Key facts

- **Pipeline per chunk** (one match minute of one player, `min(floor(t / 60), 89)`): Interpreter (labels code-built facts) -> Moments (tone and a reason; importance stays code-set) -> Commentator (one neutral English line per moment) -> Fact Guard (code validator; the model fixes a rejected line; still failing becomes a template) -> Personalizer (the four variants, checked again, then fall back to the checked English line or a Spanish template) -> Voice Director (one emotion style per line) -> Speech (plain code). A failed or invalid model answer retries once, then that role falls back; a spend limit skips the remaining model calls and the moments become template lines (trace reason `cap`).
- **Cadence** (`agents/config.py`, owner decisions Oct 27): at least 5 s between lines; a reaction 8 s after a goal; after **25 s** of silence a quiet-spell line describes the play around the ball (preferring an event within 25 m of the selected player), and at most every 3 minutes a stat line on one rotating topic (distance, rating, activity; activity only when it changed). **Every non-zero rating-log row, positive or negative, however small, gets a line** (the old +-0.10 trigger is gone): a row too close to the previous line waits up to 10 s or is said with the previous rating line, never dropped. Lima gets 245 lines, about one every 22 s; a goalkeeper about 227.
- **Voices (owner, by ear, all male):** English `en-GB-Ollie:DragonHDOmniLatestNeural` (Casual and Analyst), Spanish `es-MX-Jorge:DragonHDOmniLatestNeural` (both), set in `.env` (four `SPEECH_VOICE_*` variables). Omni accepts `mstts:express-as` styles and `temperature;top_p;cfg_scale`; the plain HD voices ignore all prosody. $22 per 1M characters. A line is 3 to 8 s (average 4.1 s, 24 KB at 48 kbps).
- **Emotions (owner):** all 14 approved styles kept. Code decides what is allowed, the Voice Director (GPT-4.1 mini) picks one: the commentators are Azure City home commentators, so the style fits the side (good, bad or neutral for Azure City), the ball's danger (`danger_at`), a mood from recent goals and big moments that carries from line to line and fades (`MOOD_TAU_S` 75), cards and goals are big, and only 85' or later may name the minute. Hyped, not calm: a Fact Guard rule rejects "calmly", "quietly", "steadily".
- **Audio in the browser:** no crowd ducking (owner), the crowd at a steady 60%, the voice louder near a goal and on big lines through a limiter, a new line waits for the clip still playing (dropped after 6 s; a big line cuts in), and commentary exists only at 1x.
- **Model:** `gpt-4.1-mini`, Global Standard, East US, v1 endpoint (`/openai/v1/`, no api-version, deployment name in the request body). Retirement April 2027.
- **Storage:** plain files. Pre-generated: `data/commentary/<match>/<player>/<mode>_<lang>_<chunk>.json` (+ `.trace.json`, `recap_<mode>_<lang>.json`) and `data/audio/<hash>.mp3`. On-demand: `<PERSIST_DIR>/commentary_ondemand/` (default `data/`; an Azure Files share in production). Lookup: pre-generated, on-demand, generate (under the cap; the caller gets 202 `preparing`, retry after 3 s), template.
- **Spend control:** every live call appends a line to `<PERSIST_DIR>/spend_ledger.jsonl` (gitignored); `python scripts/spend.py` prints the total. Server: one **all-time** cap `LIVE_CAP_USD` on model plus voice (0 means off; a missing price also means off; totals are read once and kept in memory). It replaced two daily caps and the per-IP limit (owner, Oct 27): every chunk is cached for good, so total spend has a ceiling (about $123 for every player of all three matches) and the cap sits just above it. Scripts: `--max-usd` (default 5) and `--max-chars` stop a run before the call that would pass the limit, and a cap-stopped chunk is never stored.
- **Measured (Oct 27):** Lima's full run **$1.76** (85 new minutes, four variants, four recaps) plus a re-run of the 55 minutes whose schedule changed when every rating change got a line **$1.19**; about $0.021 a minute for all four variants, about half of it voice. All-time ledger: **$4.07** (model $1.37, voice $2.70) including earlier tests; the first voice samples (about $0.05) ran before the ledger existed. Line quality: roughly 97% of lines passed Fact Guard or were fixed by the model; about 3% fell back to templates (mostly minutes 50, 52, 55 and 84).
- **Sizes:** 966 voice clips, 25 MB; commentary, traces and recaps 2.8 MB (90 minutes x 4 variants x (chunk + trace) and four recaps). Roughly 28 MB for one player, so about 1.85 GB for all 66 player-matches.

## Rules for later phases

- **Pre-generate only `md38_title_decider` for `azc_09`.** Never other players or matches by script (about $1.9 each); other players are generated live by visitors and cached. If you change a prompt or the schedule, delete the stored chunks you want regenerated (and later the audio nothing uses: list every `/audio/<hash>.mp3` referenced under `data/commentary/` and delete the rest).
- **Never read or edit `.env`** (owner rule, denied in `.claude/settings.local.json`). Scripts load it. `.env.example` still needs the owner's edits: remove `DAILY_LLM_CAP_USD`, `DAILY_SPEECH_CAP_CHARS`, `GEN_RATE_LIMIT_PER_MIN` and `AZURE_OPENAI_API_VERSION`; add `LIVE_CAP_USD=0`, `PERSIST_DIR=` and `SPEECH_PRICE_PER_1M_CHARS=22`.
- **Tests never touch Azure.** Use `tests/fakes.py` (`FakeLLM`, `FakeSpeech`). Every live run goes through `Budget` so it lands in the ledger.
- **Numbers stay in code.** Facts are built in `agents/inputs.py`; the model copies numbers from fact values and Fact Guard rejects any that are not there. Don't let an agent compute one.
- After any change to `agents/models.py`: `python scripts/export_schemas.py`, then `npm run gen:types` in `web/`.
- `app/main.py` mounts `web/dist` at `/` when it exists (and `/audio/crowd/*` comes from there). Keep the audio proxy key `^/audio/(?!crowd/)` in dev.

## Data traps

- A goal line is emitted at the kick's second; the frontend shifts it to `shownAt`. A backend consumer that wants the reveal time must apply the same flight formula.
- Template lines have no audio (`audio_url` null) and their traces live only in memory (up to 4,000, oldest dropped); stored chunks keep theirs next to the chunk file.
- The line id is `match.player.mode.lang.chunk.index`, and the trace route finds the file from it. Voice clips are named by a hash of (text, voice, ssml), so the same sentence is voiced once, and a changed voice or style setting orphans the old clips.
- A Spanish variant never falls back to English: it falls back to a Spanish template.
- Fact Guard cannot catch subjective claims ("what a legend"), only unsupported numbers, names, actions, early results, score claims ("equalise" only when level), flat words, wording rules and units. Initials ("G. Lima") are stripped in code, not rejected.
- A rating change's wording must match its sign: the fallback templates have separate "went down" frames, with a test.

## Accepted limitations

- The Interpreter and Moments agents are thin by design (facts, timing and importance are code).
- Some play lines read awkwardly ("Redmond United passes near Azure City's box now"); the owner listens and decides.
- Clip length is estimated from bytes at 48 kbps. I cannot hear audio: voice quality, pacing and emotion were judged by the owner by ear.

## Not done (with reason)

- Pre-generation of other players or matches: by cost; they are generated live and cached (Phase 4).
- The saved-replay fallback for the live demo.

## How to run

```bash
source .venv/bin/activate
pytest                                    # 180 tests, no Azure calls
uvicorn app.main:app --port 8000          # backend (template lines without keys; live AI needs keys and LIVE_CAP_USD above 0)
python scripts/spend.py                   # running Azure cost from the ledger
python scripts/pregenerate.py --chunks 38,88 --max-usd 0.40     # small measured batch, all four variants
cd web && source ~/.nvm/nvm.sh && nvm use 22 && npm run dev     # http://localhost:5173 (proxies to :8000)
npm test && npx tsc -b                    # 49 tests, typecheck
```

## Open items handed on

- Owner: fix `.env.example`; keep listening to Lima's commentary (play lines, emotion, Spanish) and say what to change; decide whether Lima's generated files stay committed to git.
- Phase 4 (done): `docs/phases/phase-4.md`.
