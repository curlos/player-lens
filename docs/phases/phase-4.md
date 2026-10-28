# Phase 4 handoff: Docker and Azure deploy (done Oct 28, 2026; live at the URL below)

> Short orientation notes for the next phase's session: what exists, where, and what not to break. This is a summary, not a substitute: still read CLAUDE.md, PRODUCT.md, ARCHITECTURE.md, TASKS.md, `docs/decisions.md`, the specs your phase prompt lists, `docs/phases/phase-1.md` to `phase-3.md` and the `docs/ui/` images. The specs win over this file.

## What was built

| Piece | Where |
| --- | --- |
| Multi-stage image: the React build, the FastAPI backend, `sim/`, `rating/`, `contracts/`, the match files and Lima's pre-generated commentary and audio; runs `uvicorn` on port 8000, one worker, as root | `Dockerfile`, `.dockerignore` |
| Deploy script: registry, build and push for `linux/amd64`, registry credentials, the Azure Files share, secrets, the app spec (image, size, replicas, port, volume, environment), health wait; `--dry-run`, `--live-cap`, `--min-replicas`, `--skip-build --image-tag` (rollback) | `scripts/deploy.py` |
| Runtime writes in one place: `PERSIST_DIR` (the on-demand cache and the spend ledger), one all-time `LIVE_CAP_USD`, cached ledger totals, no per-visitor rate limit | `app/settings.py`, `app/budget.py`, `app/cache.py`, `app/main.py` |
| Cost-proof tests (fake model and voice, count every call): Lima's 364 minutes and recaps make zero calls even with live AI on; another player's minute is generated once, then served free, also after a restart on the same share | `tests/test_cost_proof.py`, `tests/test_api.py` |
| Docs: deployment spec (image, resources, costs, deploy, rollback, persistent cache), README "Deploy" section, decisions, phase notes | `specs/deployment.md`, `README.md`, `docs/decisions.md` |

## Key facts

- **Live URL:** https://player-lens.wittysea-a332ed57.eastus.azurecontainerapps.io (port 8000 behind external ingress).
- **Azure resources** (all in `player-lens-rg`, East US): Container App `player-lens` in environment `player-lens-env` (Consumption plan, 0.5 vCPU, 1 GiB, min and max replicas 1); Container Registry `playerlensacr` (Basic); storage account `playerlensstore` with classic SMB share `persist` (Transaction optimized, no backup) mounted at `/mnt/persist`; Log Analytics workspace `workspaceplayerlensrg89e9`; the model and Speech resources from Phase 3. The owner made the storage, environment and app in the portal; `scripts/deploy.py` made the registry.
- **What the image holds vs the share:** Lima's commentary, traces and voice clips are baked into the image (copied from the local `data/` at build time, so they must exist locally or come from git). The share holds only what visitors generate for other players (text, traces, clips) and `spend_ledger.jsonl`. Keys are Container Apps secrets (`openai-key`, `speech-key`) referenced from the environment; they never enter the image, the share or any output.
- **`LIVE_CAP_USD` is an app setting, not part of the image.** It is **130** now (owner, Oct 28). `scripts/deploy.py` keeps the app's current value unless `--live-cap` is passed. Change it alone with `az containerapp update -n player-lens -g player-lens-rg --set-env-vars LIVE_CAP_USD=<n>` (a new revision, about a minute).
- **Verified live (Oct 28):** the site, Lima's stored lines and clips (including the new negative rating moments at 86'), crowd clips and recaps; `/health` shows the model and Speech configured. With a $1 cap, live generation made 35 minutes for two other players (the Azure goalkeeper and #3 Ferreira) at about $0.006 a minute, **one generation per player and minute, none paid twice**; rewatching, and a revision restart, served them from the share with no new ledger line. Lima caused no live calls (the share was empty while the owner watched him with live AI on).
- **Costs** (Azure Retail Prices, East US): container app about $10 a month idle (about $33 if billed active all month), registry $5, Azure Files and logs about $0; live AI at most $130 once (the cap). Budget $160 with alerts.

## Rules for later work

- Build only with `--platform linux/amd64` (Apple Silicon). Deploy with `python scripts/deploy.py` (dry-run first); never put a key in an argument you print, a file or the repo (the script masks them).
- A redeploy must not lower or reset the live cap by accident (the script keeps it). The spend ledger on the share is what the cap counts: never delete it while live AI is on.
- Keep one replica: the per-chunk generation locks and the ledger totals live in the one process.
- **Never mount the share over `data/`** (it would hide Lima's baked files); it is mounted at `/mnt/persist` and `PERSIST_DIR` points there.
- Tests never call Azure; the cost-proof tests use the real `data/` folder read-only.

## Data traps

- The subscription needed `Microsoft.ContainerRegistry` registered once before the registry could be created (`az provider register --namespace Microsoft.ContainerRegistry --wait`).
- The `containerapp` CLI extension installs as a preview version; that is expected.
- Browsing to a minute nobody has watched makes the browser ask for that minute plus its neighbours, so a jump shows "Preparing commentary" for a few seconds and the panel asks again every 3 s (many 202 answers in the logs are normal).
- `az containerapp logs show` returns only the latest lines (about 300); the ledger on the share is the complete record. Download it with `az storage file download` (key fetched with `az storage account keys list`, never printed) and read it with `PERSIST_DIR=<folder> python scripts/spend.py`.
- Azure's Cost analysis lags 8 to 24 hours behind the ledger.

## Not done (with reason)

- The owner's gate: whether Lima's generated files stay committed to git (a clean clone has no AI commentary without them; the deploy itself only needs them in the local folder).
- `scripts/sync_cache.py` (copy the share to the local machine and back): saved for later by the owner.
- The saved-replay fallback; a custom domain (not planned).
- A check of Azure Cost analysis and the container's CPU graph, to confirm the app is billed at the idle rate (due the day after the deploy).

## How to run

```bash
python scripts/deploy.py --dry-run                         # every step, nothing changed
python scripts/deploy.py                                   # build, push, deploy (keeps the live cap)
python scripts/deploy.py --skip-build --image-tag <tag>    # roll back
python scripts/deploy.py --min-replicas 0                  # after judging: sleep when idle
az containerapp logs show -n player-lens -g player-lens-rg --tail 100 --type console
docker build --platform linux/amd64 -t player-lens . && docker run --platform linux/amd64 -p 8001:8000 player-lens   # test the image locally
```

## Open items handed on

- Owner: edit `.env.example` (see `docs/phases/phase-3.md`); listen to the live site (Lima at 39', 64', 86', 89', and another player); decide on committing Lima's files; after Nov 10 say so and run the sleep-when-idle and registry-delete commands in `specs/deployment.md`.
- Next: check Cost analysis the day after the deploy; the sync script; fixes the owner finds in the live commentary.
