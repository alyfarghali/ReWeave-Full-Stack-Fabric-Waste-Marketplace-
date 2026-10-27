"""Backend configuration loaded from environment variables.

Secrets live in backend/.env (or the repo-root .env) locally and must never be
committed. Every other module reads configuration through ``get_settings()``
instead of calling ``os.getenv`` directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


def load_env_files() -> None:
    """Load backend/.env first, then the repo-root .env for anything still unset."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv(REPO_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _env_bool(name: str, default: bool) -> bool:
    return _env(name, str(default)).lower() in {"1", "true", "yes", "on"}


DEFAULT_SECRET_KEY = "reweave-dev-secret-do-not-use-in-prod"


@dataclass(frozen=True)
class Settings:
    # Database: Supabase Postgres in production, local SQLite for offline dev.
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", "sqlite:///./scraps.db"))

    # Seed the three demo logins and the buyer catalog into an empty database.
    seed_demo_data: bool = field(default_factory=lambda: _env_bool("SEED_DEMO_DATA", True))

    # HTTP: browser origins allowed to call the API directly (the Vite dev
    # server proxies /api, so this only matters for split-origin deployments).
    cors_origins: list[str] = field(
        default_factory=lambda: _env_list("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    )

    # Built frontend (frontend/dist) to serve from the API process, so one
    # container hosts the whole app. Unset in development, where Vite serves it.
    frontend_dist_dir: str = field(default_factory=lambda: _env("FRONTEND_DIST_DIR"))

    # IANA timezone for human-readable timestamps (admin scan-run labels).
    display_timezone: str = field(default_factory=lambda: _env("DISPLAY_TIMEZONE", "America/New_York"))

    # Auth
    secret_key: str = field(default_factory=lambda: _env("SECRET_KEY", DEFAULT_SECRET_KEY))
    token_expire_hours: int = field(default_factory=lambda: int(_env("TOKEN_EXPIRE_HOURS", "8")))

    # OpenRouter (vision LLM, destination naming, assistant chat)
    openrouter_api_key: str = field(default_factory=lambda: _env("OPENROUTER_API_KEY"))
    openrouter_vision_models: list[str] = field(
        # Fast model first; the others stay as quality fallbacks if it fails.
        default_factory=lambda: _env_list(
            "OPENROUTER_VISION_MODELS",
            "google/gemini-2.5-flash,anthropic/claude-sonnet-4.6,openai/gpt-4o",
        )
    )
    openrouter_timeout_s: int = field(default_factory=lambda: int(_env("OPENROUTER_TIMEOUT_S", "60")))
    assistant_model: str = "openai/gpt-4o-mini"

    # Replicate SAM segmentation
    replicate_api_token: str = field(default_factory=lambda: _env("REPLICATE_API_TOKEN"))
    replicate_sam_model: str = field(
        default_factory=lambda: _env("REPLICATE_SAM_MODEL", "lucataco/segment-anything-2")
    )
    # When set (an "owner/deployment-name" slug), SAM calls route to a
    # dedicated always-warm deployment instead of the public model, which
    # removes the cold-start delay before a scan.
    replicate_deployment: str = field(default_factory=lambda: _env("REPLICATE_DEPLOYMENT"))

    # Vision pipeline tuning
    aruco_marker_size_cm: float = field(default_factory=lambda: float(_env("ARUCO_MARKER_SIZE_CM", "5.0")))
    aruco_marker_id: int = field(default_factory=lambda: int(_env("ARUCO_MARKER_ID", "23")))
    max_image_dimension: int = field(default_factory=lambda: int(_env("VISION_MAX_IMAGE_DIMENSION", "1600")))
    max_pieces: int = field(default_factory=lambda: int(_env("VISION_MAX_PIECES", "35")))

    @property
    def uses_default_secret(self) -> bool:
        return self.secret_key == DEFAULT_SECRET_KEY


@lru_cache
def get_settings() -> Settings:
    load_env_files()
    return Settings()
