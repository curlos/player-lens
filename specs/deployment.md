# Spec: Deployment and Environment

Oct 25, 2026 · @Carlos Martinez

## Purpose and setup

Player Lens ships as one Docker container on Azure Container Apps, serving the built React app, the static match files and the API. This spec lists every environment variable, the image build, the Azure resources and the deploy steps.

- One container, one public URL, one replica (min 1, max 1) so the on-demand cache and spend counter stay in one place (the per-chunk generation lock and the cached spend totals live in that one process).
- Runtime writes (the on-demand cache and the spend ledger) go to an Azure Files share mounted at `PERSIST_DIR`, so they survive restarts and redeploys and every chunk is paid for once (see "Persistent cache").
- All secrets come from environment variables (Container Apps secrets in production, a git-ignored `.env` locally). Nothing secret is ever committed, logged or sent to the browser.
- The app must start and play the full hero match with no Azure keys set (cache and template fallback only).

## Environment variables

Committed as `.env.example` with empty values. `S` = secret.

| Name | S | Default | Purpose |
| --- | --- | --- | --- |
| `AZURE_OPENAI_ENDPOINT` |  | none | Foundry / Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | S | none | Key for the model deployment |
| `AZURE_OPENAI_DEPLOYMENT` |  | none | Deployment name of the small model |
| `AZURE_OPENAI_API_VERSION` |  | not needed | Only for older deployments-style endpoints; the v1 endpoint (`https://<resource>.services.ai.azure.com/openai/v1/`) takes none, and only the endpoint's host is used |
| `LLM_PRICE_IN_PER_1M` |  | 0 | Dollars per 1M input tokens, for the cap |
| `LLM_PRICE_OUT_PER_1M` |  | 0 | Dollars per 1M output tokens, for the cap |
| `LIVE_CAP_USD` |  | 0 | All-time dollars (model + voice) that visitors may trigger; 0 means cache and templates only. Not daily: the cache bounds total spend, so this sits just above that ceiling as a safety net |
| `AZURE_SPEECH_KEY` | S | none | Azure AI Speech key |
| `AZURE_SPEECH_REGION` |  | none | Speech region, for example `eastus` |
| `SPEECH_VOICE_EN_CASUAL` / `_EN_ANALYST` / `_ES_CASUAL` / `_ES_ANALYST` |  | none | Voice names per mode and language |
| `SPEECH_PRICE_PER_1M_CHARS` |  | 22 | Dollars per 1M characters for the cap math (HD voices 22, standard neural 15) |
| `DATA_DIR` |  | `./data` | Match files and the pre-generated commentary and audio (baked into the image, read-only) |
| `PERSIST_DIR` |  | `DATA_DIR` | Runtime writes: `commentary_ondemand/` (text and audio) and `spend_ledger.jsonl`. In production the Azure Files mount, `/mnt/persist` |
| `ALLOWED_ORIGINS` |  | same origin | CORS origins (dev server only) |
| `LOG_LEVEL` |  | `INFO` | Logging level |

Rules:

- Missing optional values must never crash startup; `/health` lists which services are off.
- Values are read once at startup through one settings module (`app/settings.py`); no other file reads `os.environ`.
- The frontend gets no secrets and needs no env vars; it calls same-origin routes only.

## Docker image

Multi-stage `Dockerfile` at the repo root:

1. **Web stage** (`node:22-slim`): `npm ci` and `npm run build` in `web/`, output to `web/dist/`.
2. **Runtime stage** (`python:3.13-slim`, the version the tests run on): install `requirements.txt`, copy `app/`, `agents/`, `sim/`, `rating/`, `contracts/` (the code imports `sim` and `rating`, and `sim/validate.py` reads `contracts/`), `data/` (match files plus the pre-generated commentary and audio) and the built `web/dist/`, which `app/main.py` serves at `/` (the crowd clips under `/audio/crowd/` come from there).
3. Start with `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1`. The container runs as root so the SMB share is writable without uid/gid mount options.

Build on an Apple Silicon Mac with `--platform linux/amd64`, or the image won't run on Container Apps. Measured Oct 27: the image is about 116 MB compressed.

Rules:

- `.dockerignore` excludes `.env*`, `.git`, `.venv`, `web/node_modules`, `web/dist` (rebuilt in the image), `tests`, `docs`, `specs`, `scripts`, `data/spend_ledger.jsonl`, `data/commentary_ondemand/` and `data/seed_search.jsonl`. The pre-generated `data/commentary/` and `data/audio/` ship in the image: the build copies them from the local `data/` folder, so the build machine must have them (they are normally committed to git, which is how a clean clone gets them; whether to keep committing them is an open owner decision).
- The image must contain the pre-generated hero match, default star commentary and audio, so a cold container serves them with no Azure calls.
- Target image size under 1 GB; check that `data/` stays small (positions files are integer arrays, a few MB per match).

## Azure resources and deploy steps

Resources, all in one resource group in one region close to the Speech and model resources:

Actual names (Oct 27-28): resource group `player-lens-rg`, East US.

- Foundry project with one `gpt-4.1-mini` deployment (Global Standard) and an Azure AI Speech resource (made first, with the keys in `.env`).
- Storage account `playerlensstore` (Standard, LRS, Azure Files, pay-as-you-go) with one classic SMB share `persist` (Transaction optimized, no backup) for the persistent cache (see "Persistent cache").
- Container Apps environment `player-lens-env` (Consumption plan only: no Dedicated profile, no custom network) and the Container App `player-lens`: external ingress, port 8000, min and max replicas 1, 0.5 vCPU and 1 GiB. Created in the portal with the Hello World quickstart image as a placeholder.
- Azure Container Registry `playerlensacr` (Basic, admin user on), created by `scripts/deploy.py`. The subscription must have the `Microsoft.ContainerRegistry` resource provider registered once (`az provider register --namespace Microsoft.ContainerRegistry --wait`).
- Budget: $160 with alerts (owner, Oct 27), covering the live cap and hosting.

Hosting cost (Azure Retail Prices, East US, Oct 27; Consumption plan: 180,000 vCPU-s, 360,000 GiB-s and 2 million requests free a month; idle $0.000003 per vCPU-s and GiB-s, active $0.000024 per vCPU-s): container app always on about $10 a month while idle (about $33 if it is billed active the whole month, because a replica is active above 0.01 cores or 1,000 bytes a second), registry Basic $0.167 a day (about $5 a month), Azure Files under $0.15, Log Analytics free under 5 GB. The $0.10 an hour environment "management" meter applies only to Dedicated plans, private endpoints and planned maintenance, none of which we use. Check Cost analysis the day after a deploy.

Deploy (`scripts/deploy.py`, needs `az login`, the `containerapp` extension, Docker running and a filled `.env`; `--dry-run` prints every step and changes nothing):

1. Create the registry if missing, `az acr login`, build for `linux/amd64`, push `playerlensacr.azurecr.io/player-lens:<git sha>-<UTC time>`.
2. Give the app the registry credentials (`az containerapp registry set`), attach the share to the environment (`az containerapp env storage set`, the storage key goes straight from `az` into the command and is never printed) and store the model and Speech keys as secrets (`az containerapp secret set`).
3. Update the app from a YAML (JSON) spec: the image, 0.5 vCPU, 1 GiB, min replicas 1 and max 1, port 8000, the share as an `AzureFile` volume mounted at `/mnt/persist`, and the environment: a whitelist of settings from `.env` (endpoint, deployment, prices, speech region, voices), the two keys as secret references, `PERSIST_DIR=/mnt/persist`, `LIVE_CAP_USD` and `LOG_LEVEL`. Local values such as `DATA_DIR` are never copied.
4. Wait for `/health`.

`LIVE_CAP_USD`: a first deploy starts at 0 (live AI off) and later deploys keep whatever the app has; `--live-cap N` sets it (a setting on the app, not in the image, so it survives new images). Verify the pre-generated path and the share first, then set it to the full-coverage ceiling plus a margin (about 130; see "Persistent cache"). Or change it alone: `az containerapp update -n player-lens -g player-lens-rg --set-env-vars LIVE_CAP_USD=130`.

Rollback: every image keeps its tag in the registry, so `python scripts/deploy.py --skip-build --image-tag <tag>` re-deploys an earlier one.

After judging (Nov 10): `python scripts/deploy.py --min-replicas 0` so it sleeps when idle (about $0 unused; the first visitor then waits 10 to 30 s), and delete the registry (`az acr delete -n playerlensacr -g player-lens-rg`) to stop the $5 a month.

First deploy verified (Oct 28): `/health` ok, Lima's stored lines and clips, crowd clips and recaps served from the image; live AI at a $1 cap generated 35 minutes for two other players once each (ledger: one generation per player and minute, none paid twice); rewatching and a revision restart served them from the share with no new ledger lines.

## Persistent cache

The container's own disk is wiped on every restart and redeploy, so without a share each wipe would make visitors pay again for chunks already generated, and would reset the spend ledger the cap reads. An Azure Files share fixes both with no code change beyond `PERSIST_DIR`.

**Why Azure Files.** It is the only permanent storage Container Apps can mount (Blob Storage and NetApp can't be mounted), so the app keeps reading and writing plain files. Blob Storage would need upload code and its own URL serving. Cloudinary is a media CDN, needs SDK code and keys, and is the wrong home for a JSON ledger; at about 24 KB per clip and modest traffic, a CDN buys nothing. A database is out of scope.

**Ceiling.** Each chunk is generated once and kept, so total live spend is bounded by full coverage: 3 matches x 22 players x 4 variants x 90 chunks. The measured full run for one player is $1.76 (Oct 27; projected $1.86 for all 90 chunks), so full coverage is about $123 once, then $0. `LIVE_CAP_USD` sits just above it (about 130) as a safety net against bugs. There is no per-visitor limit: the viewer only asks for commentary at 1x, and a burst is slowed by the model's own rate limit.

**Size and cost** (Azure retail prices, East US, Hot LRS, Oct 27 2026: $0.0287 per GB a month, $0.0052 per 10,000 reads, $0.065 per 10,000 writes):

- One player's full match: about 920 clips (about 24 KB and 4 s each, 48 kbps MP3) is about 22 MB of audio, plus about 3 MB of JSON.
- Full coverage of all three matches: about 66 players-worth, so about 1.7 GB: about $0.05 a month to store.
- Filling it once is a few hundred thousand writes, about $3 at most. Serving a cached chunk is a handful of reads, so even 100,000 page loads cost cents.

**Layout.** The share is mounted at `/mnt/persist` (`PERSIST_DIR=/mnt/persist`), never over `data/`: a mount hides whatever the image has at that path, and `data/` holds the baked hero files.

```
/mnt/persist/
  commentary_ondemand/<match>/<player>/<mode>_<lang>_<chunk>.json   (+ .trace.json, recap_*.json)
  commentary_ondemand/audio/<hash>.mp3
  spend_ledger.jsonl
```

**Setup** (once, portal or CLI, same resource group and region):

1. Storage account: Standard, LRS, StorageV2. Create a **classic** file share named `persist` (SMB, Hot tier, quota 5 GiB). Container Apps can't mount the newer `Microsoft.FileShares` resource type.
2. Add the share to the Container Apps environment: `az containerapp env storage set --name <env> --resource-group <rg> --storage-name persist --storage-type AzureFile --azure-file-account-name <account> --azure-file-share-name persist --access-mode ReadWrite`, with either `--azure-file-identity system` (managed identity, in preview: needs the environment's system identity, "Managed Identity for SMB" on the account and the "Storage File Data SMB MI Admin" role) or `--azure-file-account-key <key>` (simplest). Paste the key only into that command or the portal, never into chat or the repo.
3. Mount it in the app (exported YAML, `az containerapp update --yaml app.yaml`, or the portal's Volumes tab): a volume `persist` with `storageType: AzureFile`, `storageName: persist`, and a volume mount at `/mnt/persist`. Set `PERSIST_DIR=/mnt/persist`.
4. If the image runs as a non-root user, add `mountOptions: uid=<uid>,gid=<gid>` (SMB has no chmod), or the app can't write.
5. Check: generate one uncached chunk, restart the revision, request it again; it must come back with no new ledger line.

Notes: writes are atomic (temp file, then rename), which SMB supports. The spend totals are read from the ledger once at startup and kept in memory, so the cap check doesn't reread a growing file over the network. Only one replica may write.

## Local development and secrets

- Backend: `uvicorn app.main:app --reload`; frontend: `npm run dev` with a proxy to the backend. Or `docker compose up` for the production-like path.
- Copy `.env.example` to `.env` (git-ignored) and fill in only what you need. With nothing filled in, the app runs on cache and templates.
- `.gitignore` includes `.env`, `data/commentary_ondemand/`, and generated audio not needed in the image.
- Before every commit to the public repo, search for keys: `git grep -nE "(api[_-]?key|secret)"` must show only variable names, never values.
- If a key is ever committed, rotate it in Azure immediately; deleting the commit is not enough.

## Pre-submission checklist

- [ ] Live URL works from a fresh browser and a phone, hero match plays start to finish
- [ ] Cold start under 15 seconds after the container scales from a restart
- [ ] Public GitHub repo has README, setup steps, `.env.example`, no secrets
- [ ] Budget alert set; `LIVE_CAP_USD` set; the share is mounted and a generated chunk survives a restart
- [ ] Demo video recorded against the live URL (under 2 minutes)
- [ ] Live link kept up through Nov 10

## Open questions

- Region choice (decided at Azure setup, based on where the model and Speech are available).
- Whether to use a registry or `az containerapp up --source` (the second is faster to set up).
- Custom domain: not planned; the default Container Apps URL is enough.
