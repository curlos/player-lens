"""The one place environment variables are read (specs/deployment.md, "Environment variables").

Missing optional values never crash startup: a service whose values are missing is simply off, and
``/health`` reports which. Nothing here is ever logged or sent to the browser. A local ``.env`` file is
loaded for development (values already in the environment win); in production the host sets the variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
# Standard HD voice price, dollars per 1M characters (azure.microsoft.com/pricing/details/speech, Oct 2026).
DEFAULT_SPEECH_PRICE_PER_1M = 22.0


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def _float(raw: str | None, default: float = 0.0) -> float:
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    openai_endpoint: str = ""
    openai_api_key: str = field(default="", repr=False)
    openai_deployment: str = ""
    llm_price_in: float = 0.0  # dollars per 1M input tokens
    llm_price_out: float = 0.0  # dollars per 1M output tokens
    live_cap_usd: float = 0.0  # all-time dollars (model + voice) visitors may trigger; 0 means no live generation
    speech_key: str = field(default="", repr=False)
    speech_region: str = ""
    speech_price_per_1m: float = DEFAULT_SPEECH_PRICE_PER_1M
    voices: dict[str, str] = field(default_factory=dict)  # "en_casual" -> voice name
    data_dir: Path = ROOT / "data"
    persist_dir: Path | None = None  # on-demand cache and spend ledger; an Azure Files mount in production (default: data_dir)
    allowed_origins: tuple[str, ...] = ()
    log_level: str = "INFO"

    @property
    def llm_base_url(self) -> str:
        """The v1 API base (no api-version needed): only the host of the configured endpoint is used."""
        host = urlparse(self.openai_endpoint)
        return f"{host.scheme}://{host.netloc}/openai/v1/" if host.netloc else ""

    @property
    def llm_configured(self) -> bool:
        return bool(self.openai_endpoint and self.openai_api_key and self.openai_deployment)

    @property
    def llm_live_allowed(self) -> bool:
        """Live generation needs a configured model, a cap above 0 and both prices (so a forgotten price can't leave spending uncapped)."""
        return self.llm_configured and self.live_cap_usd > 0 and self.llm_price_in > 0 and self.llm_price_out > 0

    @property
    def persist(self) -> Path:
        """Where runtime writes go (the on-demand cache and the spend ledger), so they can live on a mounted share."""
        return self.persist_dir or self.data_dir

    @property
    def speech_configured(self) -> bool:
        return bool(self.speech_key and self.speech_region)

    def voice(self, mode: str, lang: str) -> str:
        return self.voices.get(f"{lang}_{mode}", "")

    def health(self) -> dict[str, object]:
        """Which services are on, never any values."""
        return {
            "ok": True,
            "llm_configured": self.llm_configured,
            "llm_live_generation": self.llm_live_allowed,
            "llm_price_missing": self.llm_configured and self.live_cap_usd > 0 and not (self.llm_price_in > 0 and self.llm_price_out > 0),
            "speech_configured": self.speech_configured,
            "speech_live_audio": self.speech_configured and self.live_cap_usd > 0,
        }


def load_settings(env: dict[str, str] | None = None, env_file: Path | None = ROOT / ".env") -> Settings:
    """Settings from ``env`` (default: the process environment over the .env file). Pass ``env_file=None`` in tests."""
    if env is None:
        env = {**(_read_env_file(env_file) if env_file else {}), **os.environ}
    g = env.get
    return Settings(
        openai_endpoint=g("AZURE_OPENAI_ENDPOINT", ""),
        openai_api_key=g("AZURE_OPENAI_API_KEY", ""),
        openai_deployment=g("AZURE_OPENAI_DEPLOYMENT", ""),
        llm_price_in=_float(g("LLM_PRICE_IN_PER_1M")),
        llm_price_out=_float(g("LLM_PRICE_OUT_PER_1M")),
        live_cap_usd=_float(g("LIVE_CAP_USD")),
        speech_key=g("AZURE_SPEECH_KEY", ""),
        speech_region=g("AZURE_SPEECH_REGION", ""),
        speech_price_per_1m=_float(g("SPEECH_PRICE_PER_1M_CHARS"), DEFAULT_SPEECH_PRICE_PER_1M),
        voices={f"{lang}_{mode}": g(f"SPEECH_VOICE_{lang.upper()}_{mode.upper()}", "") for lang in ("en", "es") for mode in ("casual", "analyst")},
        data_dir=Path(g("DATA_DIR") or ROOT / "data"),
        persist_dir=Path(g("PERSIST_DIR")) if g("PERSIST_DIR") else None,
        allowed_origins=tuple(o.strip() for o in g("ALLOWED_ORIGINS", "").split(",") if o.strip()),
        log_level=g("LOG_LEVEL", "INFO"),
    )
