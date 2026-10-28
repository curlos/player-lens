"""Deploys Player Lens to Azure Container Apps (specs/deployment.md, "Azure resources and deploy steps").

Needs the Azure CLI signed in (``az login``), the containerapp extension, Docker running, and a filled ``.env``.
Run from the repo root with the venv active:

    python scripts/deploy.py --dry-run          # print every step, change nothing
    python scripts/deploy.py                    # build, push and deploy, keeping the app's current LIVE_CAP_USD (0 on a first deploy)
    python scripts/deploy.py --live-cap 130     # same, setting the all-time live spend cap to $130 (0 turns live generation off)
    python scripts/deploy.py --skip-build --image-tag <tag>   # roll back to (or re-deploy) an image already pushed

Every step can run again safely. Secrets (the model and Speech keys, the storage and registry passwords) go from
``app.settings`` or ``az`` output straight into ``az`` arguments: they are never printed, logged or written to disk,
and they never enter the image. Only a whitelist of settings is copied to the app; local values such as ``DATA_DIR``
or a local ``LIVE_CAP_USD`` are not.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.settings import load_settings  # noqa: E402

# Azure resources (created by the owner in the portal, Oct 27; the registry is created here on first run).
RESOURCE_GROUP = "player-lens-rg"
APP = "player-lens"
ENVIRONMENT = "player-lens-env"
STORAGE_ACCOUNT = "playerlensstore"
SHARE = "persist"  # classic SMB share; also the environment storage name and the volume name
REGISTRY = "playerlensacr"
IMAGE = "player-lens"
PERSIST_MOUNT = "/mnt/persist"
PORT = 8000
CPU, MEMORY = 0.5, "1Gi"


def run(args: list[str], *, secrets: tuple[str, ...] = (), capture: bool = False, dry: bool = False, change: bool = True) -> str:
    """Runs one command, printing it with every secret value masked. With ``dry``, commands that change things are only printed."""
    shown = " ".join("***" if a in secrets else (a.split("=", 1)[0] + "=***" if any(s and s in a for s in secrets) else a) for a in args)
    print(f"$ {shown}", flush=True)
    if dry and change:
        return ""
    done = subprocess.run(args, check=False, text=True, capture_output=True)
    if done.returncode != 0:
        err = done.stderr
        for s in secrets:
            err = err.replace(s, "***") if s else err
        sys.exit(f"failed ({done.returncode}): {err.strip()[-800:]}")
    return done.stdout.strip() if capture else ""


def az(*args: str, **kw) -> str:
    return run(["az", *args, "--only-show-errors"], **kw)


def default_tag() -> str:
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True, capture_output=True).stdout.strip() or "local"
    return f"{sha}-{datetime.now(timezone.utc):%Y%m%d%H%M}"


def ensure_registry(dry: bool) -> str:
    """The Basic registry (about $5/month), with its admin user on so the app can pull with a password secret."""
    exists = subprocess.run(["az", "acr", "show", "-n", REGISTRY, "-g", RESOURCE_GROUP, "--only-show-errors"],
                            text=True, capture_output=True).returncode == 0
    if not exists:
        az("acr", "create", "-n", REGISTRY, "-g", RESOURCE_GROUP, "--sku", "Basic", "--admin-enabled", "true", dry=dry)
    return f"{REGISTRY}.azurecr.io"


def build_and_push(server: str, tag: str, dry: bool) -> str:
    ref = f"{server}/{IMAGE}:{tag}"
    az("acr", "login", "-n", REGISTRY, dry=dry)
    run(["docker", "build", "--platform", "linux/amd64", "-t", ref, str(ROOT)], dry=dry)
    run(["docker", "push", ref], dry=dry)
    return ref


def attach_registry(server: str, dry: bool) -> None:
    password = "" if dry else az("acr", "credential", "show", "-n", REGISTRY, "--query", "passwords[0].value", "-o", "tsv", capture=True, change=False)
    az("containerapp", "registry", "set", "-n", APP, "-g", RESOURCE_GROUP, "--server", server, "--username", REGISTRY,
       "--password", password, secrets=(password,), dry=dry)


def attach_share(dry: bool) -> None:
    key = "" if dry else az("storage", "account", "keys", "list", "--account-name", STORAGE_ACCOUNT, "-g", RESOURCE_GROUP,
                            "--query", "[0].value", "-o", "tsv", capture=True, change=False)
    az("containerapp", "env", "storage", "set", "-n", ENVIRONMENT, "-g", RESOURCE_GROUP, "--storage-name", SHARE,
       "--storage-type", "AzureFile", "--azure-file-account-name", STORAGE_ACCOUNT, "--azure-file-account-key", key,
       "--azure-file-share-name", SHARE, "--access-mode", "ReadWrite", secrets=(key,), dry=dry)


def set_secrets(s, dry: bool) -> None:
    if not (s.openai_api_key and s.speech_key):
        sys.exit("AZURE_OPENAI_API_KEY and AZURE_SPEECH_KEY must be set in .env")
    pairs = [f"openai-key={s.openai_api_key}", f"speech-key={s.speech_key}"]
    az("containerapp", "secret", "set", "-n", APP, "-g", RESOURCE_GROUP, "--secrets", *pairs,
       secrets=(s.openai_api_key, s.speech_key), dry=dry)


def app_env(s, live_cap: float) -> list[dict]:
    """The app's environment: a whitelist of non-secret settings, the two keys as secret references, and production paths."""
    plain = {
        "AZURE_OPENAI_ENDPOINT": s.openai_endpoint,
        "AZURE_OPENAI_DEPLOYMENT": s.openai_deployment,
        "LLM_PRICE_IN_PER_1M": s.llm_price_in,
        "LLM_PRICE_OUT_PER_1M": s.llm_price_out,
        "AZURE_SPEECH_REGION": s.speech_region,
        "SPEECH_PRICE_PER_1M_CHARS": s.speech_price_per_1m,
        **{f"SPEECH_VOICE_{key.split('_')[0].upper()}_{key.split('_')[1].upper()}": v for key, v in s.voices.items()},
        "PERSIST_DIR": PERSIST_MOUNT,
        "LIVE_CAP_USD": live_cap,
        "LOG_LEVEL": "INFO",
    }
    env = [{"name": k, "value": str(v)} for k, v in plain.items() if v not in ("", None)]
    return env + [{"name": "AZURE_OPENAI_API_KEY", "secretRef": "openai-key"}, {"name": "AZURE_SPEECH_KEY", "secretRef": "speech-key"}]


def current_live_cap() -> float:
    """The LIVE_CAP_USD the app has now, so a redeploy never changes it by accident (0 if the app has none yet)."""
    current = json.loads(az("containerapp", "show", "-n", APP, "-g", RESOURCE_GROUP, "-o", "json", capture=True, change=False))
    for var in current["properties"]["template"]["containers"][0].get("env") or []:
        if var["name"] == "LIVE_CAP_USD":
            return float(var.get("value") or 0)
    return 0.0


def update_app(image: str, env: list[dict], min_replicas: int, dry: bool) -> None:
    """Image, size, replicas, env and the share mount in one revision (volumes can only be set from YAML; JSON is valid YAML)."""
    current = json.loads(az("containerapp", "show", "-n", APP, "-g", RESOURCE_GROUP, "-o", "json", capture=True, change=False))
    name = current["properties"]["template"]["containers"][0]["name"]
    spec = {"properties": {"template": {
        "containers": [{"name": name, "image": image, "resources": {"cpu": CPU, "memory": MEMORY}, "env": env,
                        "volumeMounts": [{"volumeName": SHARE, "mountPath": PERSIST_MOUNT}]}],
        "scale": {"minReplicas": min_replicas, "maxReplicas": 1},
        "volumes": [{"name": SHARE, "storageType": "AzureFile", "storageName": SHARE}],
    }}}
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:  # holds secret names only, never values
        json.dump(spec, fh)
    try:
        az("containerapp", "ingress", "update", "-n", APP, "-g", RESOURCE_GROUP, "--target-port", str(PORT), dry=dry)
        az("containerapp", "update", "-n", APP, "-g", RESOURCE_GROUP, "--yaml", fh.name, dry=dry)
    finally:
        Path(fh.name).unlink(missing_ok=True)


def wait_healthy(dry: bool) -> None:
    fqdn = az("containerapp", "show", "-n", APP, "-g", RESOURCE_GROUP, "--query", "properties.configuration.ingress.fqdn",
              "-o", "tsv", capture=True, change=False)
    url = f"https://{fqdn}"
    print(f"\nURL: {url}")
    if dry:
        return
    for _ in range(60):
        # the old revision keeps answering /health while a broken new one fails to start, so wait for the new one to be ready first
        revs = az("containerapp", "show", "-n", APP, "-g", RESOURCE_GROUP, "--query",
                  "[properties.latestRevisionName, properties.latestReadyRevisionName]", "-o", "tsv", capture=True, change=False).split()
        try:
            if len(revs) == 2 and revs[0] == revs[1]:
                with urllib.request.urlopen(f"{url}/health", timeout=10) as res:
                    health = json.load(res)
                if health.get("ok") and "llm_live_generation" in health:
                    print(f"revision {revs[0]} ready; health:", json.dumps(health))
                    return
        except Exception:  # still starting
            pass
        time.sleep(5)
    sys.exit("the new revision was not ready and healthy within 5 minutes: check it in the portal or `az containerapp logs show`")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--image-tag", default=None, help="default: git short SHA plus UTC time")
    p.add_argument("--live-cap", type=float, default=None, help="all-time live spend cap in dollars (LIVE_CAP_USD); 0 means off; default: keep the app's current value")
    p.add_argument("--min-replicas", type=int, default=1, help="1 during judging (always on), 0 after (sleeps when idle)")
    p.add_argument("--skip-build", action="store_true", help="deploy an image already in the registry (--image-tag required)")
    p.add_argument("--dry-run", action="store_true", help="print every step, change nothing")
    args = p.parse_args()
    if args.skip_build and not args.image_tag:
        p.error("--skip-build needs --image-tag")
    tag = args.image_tag or default_tag()
    settings = load_settings()

    server = ensure_registry(args.dry_run)
    image = f"{server}/{IMAGE}:{tag}" if args.skip_build else build_and_push(server, tag, args.dry_run)
    attach_registry(server, args.dry_run)
    attach_share(args.dry_run)
    set_secrets(settings, args.dry_run)
    live_cap = args.live_cap if args.live_cap is not None else current_live_cap()
    update_app(image, app_env(settings, live_cap), args.min_replicas, args.dry_run)
    wait_healthy(args.dry_run)
    print(f"deployed {image} (LIVE_CAP_USD={live_cap:g}, min replicas {args.min_replicas})")


if __name__ == "__main__":
    main()
