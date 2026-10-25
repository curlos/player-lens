# Spec: Deployment and Environment

Oct 25, 2026 · @Carlos Martinez

## Purpose and setup

Player Lens ships as one Docker container on Azure Container Apps, serving the built React app, the static match files and the API. This spec lists every environment variable, the image build, the Azure resources and the deploy steps.

- One container, one public URL, one replica (min 1, max 1) so the on-demand cache and spend counter stay in one place.
- All secrets come from environment variables (Container Apps secrets in production, a git-ignored `.env` locally). Nothing secret is ever committed, logged or sent to the browser.
- The app must start and play the full hero match with no Azure keys set (cache and template fallback only).

## Environment variables

Committed as `.env.example` with empty values. `S` = secret.

| Name | S | Default | Purpose |
| --- | --- | --- | --- |
| `AZURE_OPENAI_ENDPOINT` |  | none | Foundry / Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | S | none | Key for the model deployment |
| `AZURE_OPENAI_DEPLOYMENT` |  | none | Deployment name of the small model |
| `AZURE_OPENAI_API_VERSION` |  | latest supported | API version string |
| `LLM_PRICE_IN_PER_1M` |  | 0 | Dollars per 1M input tokens, for the cap |
| `LLM_PRICE_OUT_PER_1M` |  | 0 | Dollars per 1M output tokens, for the cap |
| `DAILY_LLM_CAP_USD` |  | 0 | Daily live-generation budget; 0 means cache and templates only |
| `AZURE_SPEECH_KEY` | S | none | Azure AI Speech key |
| `AZURE_SPEECH_REGION` |  | none | Speech region, for example `eastus` |
| `SPEECH_VOICE_EN_CASUAL` / `_EN_ANALYST` / `_ES_CASUAL` / `_ES_ANALYST` |  | none | Voice names per mode and language |
| `DAILY_SPEECH_CAP_CHARS` |  | 0 | Daily Speech character budget; 0 means no live audio |
| `GEN_RATE_LIMIT_PER_MIN` |  | 3 | Uncached chunk generations per IP per minute |
| `DATA_DIR` |  | `./data` | Match files, commentary and audio caches |
| `ALLOWED_ORIGINS` |  | same origin | CORS origins (dev server only) |
| `LOG_LEVEL` |  | `INFO` | Logging level |

Rules:

- Missing optional values must never crash startup; `/health` lists which services are off.
- Values are read once at startup through one settings module (`app/settings.py`); no other file reads `os.environ`.
- The frontend gets no secrets and needs no env vars; it calls same-origin routes only.

## Docker image

Multi-stage `Dockerfile` at the repo root:

1. **Frontend stage** (node): `npm ci` and `npm run build` in `frontend/`, output to `dist/`.
2. **Runtime stage** (python 3.11 slim): install `requirements.txt`, copy `app/`, `agents/`, `sim/` (not needed at runtime but harmless), the built `dist/` as static files, and `data/` (match files plus the pre-generated commentary and audio).
3. Start with `uvicorn app.main:app --host 0.0.0.0 --port 8000`, single worker.

Rules:

- `.dockerignore` excludes `.env`, `.git`, `node_modules`, `__pycache__`, test output and `data/commentary_ondemand/` (runtime writes only). The pre-generated `data/commentary/` is not excluded and ships in the image.
- The image must contain the pre-generated hero match, default star commentary and audio, so a cold container serves them with no Azure calls.
- Target image size under 1 GB; check that `data/` stays small (positions files are integer arrays, a few MB per match).

## Azure resources and deploy steps

Resources, all in one resource group in one region close to the Speech and model resources:

- Foundry project with one small OpenAI model deployment.
- Azure AI Speech resource.
- Azure Container Registry (Basic), or build with `az containerapp up --source` and skip the registry.
- Container Apps environment and one Container App: external ingress, port 8000, min and max replicas 1, 0.5 vCPU and 1 GiB.
- A $5 budget alert on the subscription before anything is deployed.

Deploy steps:

1. Build and test locally with `docker build` and `docker run --env-file .env`.
2. Push the image (or run `az containerapp up`).
3. Set secrets with `az containerapp secret set`, then map them to env vars; set the non-secret vars directly.
4. Open the public URL, play the hero match for a minute, check `/health`.
5. Keep `DAILY_LLM_CAP_USD` at 0 until the pre-generated path is verified, then raise it to a small value (for example 2).

Redeploys use a new image tag each time; keep the last working tag so rollback is one command.

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
- [ ] Budget alert set; daily caps set to intended values
- [ ] Demo video recorded against the live URL (under 2 minutes)
- [ ] Live link kept up through Nov 10

## Open questions

- Region choice (decided at Azure setup, based on where the model and Speech are available).
- Whether to use a registry or `az containerapp up --source` (the second is faster to set up).
- Custom domain: not planned; the default Container Apps URL is enough.
