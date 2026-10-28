# Player Lens: one image with the built React app, the FastAPI backend and the pre-generated hero match
# (specs/deployment.md). Build for Azure Container Apps from an Apple Silicon Mac with:
#   docker build --platform linux/amd64 -t player-lens .

# --- 1. Web: build the React app into web/dist --------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- 2. Runtime: Python backend serving the API, the match files, the audio and the built app -------------
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ app/
COPY agents/ agents/
COPY sim/ sim/
COPY rating/ rating/
COPY contracts/ contracts/
# match files plus the pre-generated commentary and audio (runtime writes go to PERSIST_DIR, never here)
COPY data/ data/
COPY --from=web /web/dist web/dist
# Runs as root so the Azure Files (SMB) mount at PERSIST_DIR is writable without uid/gid mount options.
EXPOSE 8000
# One worker: the per-chunk generation locks and the cached spend totals live in this one process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
