"""Application configuration.

Centralised, environment-driven configuration for the Spec2Tests backend.

Values are read from process environment variables (populated from a local
``.env`` file via :mod:`python-dotenv` when present). A cached
:class:`Settings` singleton is exposed through :func:`get_settings` so the
rest of the application can depend on a single, validated configuration
object without incurring repeated environment lookups or file I/O.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

# Resolve the backend project root (the directory containing this `app` package)
# so that `.env` is located deterministically regardless of the current
# working directory the process was started from.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load variables from `.env` into the process environment. Existing
# environment variables (e.g. set by the shell, CI, or a container
# orchestrator) always take precedence and are never overridden.
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)


def _get_bool(env_var: str, default: bool) -> bool:
    """Parse a boolean-ish environment variable value."""
    raw = os.getenv(env_var)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_list(env_var: str, default: list[str]) -> list[str]:
    """Parse a comma-separated environment variable value into a list."""
    raw = os.getenv(env_var)
    if raw is None or raw.strip() == "":
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings(BaseModel):
    """Typed, validated application settings.

    Instances are constructed once (see :func:`get_settings`) from the
    current process environment.
    """

    # --- Application ---------------------------------------------------
    app_name: str = Field(default="Spec2Tests")
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)

    # --- CORS ------------------------------------------------------------
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )

    # --- Google Gemini -----------------------------------------------
    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-3.6-flash")

    # --- File upload limits ----------------------------------------------
    max_upload_size_mb: int = Field(default=10, ge=1)
    allowed_upload_extensions: list[str] = Field(
        default_factory=lambda: [".pdf", ".docx", ".txt"]
    )

    # --- Logging -----------------------------------------------------------
    log_level: str = Field(default="INFO")

    @field_validator("allowed_upload_extensions")
    @classmethod
    def _normalize_extensions(cls, value: list[str]) -> list[str]:
        """Ensure every extension is lowercase and prefixed with a dot."""
        normalized = []
        for ext in value:
            ext = ext.strip().lower()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            normalized.append(ext)
        return normalized

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = value.strip().upper()
        if upper not in valid_levels:
            raise ValueError(
                f"log_level must be one of {sorted(valid_levels)}, got {value!r}"
            )
        return upper

    @property
    def max_upload_size_bytes(self) -> int:
        """Maximum allowed upload size expressed in bytes."""
        return self.max_upload_size_mb * 1024 * 1024


def _build_settings() -> Settings:
    """Construct a :class:`Settings` instance from the current environment."""
    return Settings(
        app_name=os.getenv("APP_NAME", "Spec2Tests"),
        app_env=os.getenv("APP_ENV", "development"),
        debug=_get_bool("DEBUG", True),
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        cors_origins=_get_list(
            "CORS_ORIGINS", ["http://localhost:5173", "http://localhost:3000"]
        ),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL"),
        max_upload_size_mb=int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")),
        allowed_upload_extensions=_get_list(
            "ALLOWED_UPLOAD_EXTENSIONS", [".pdf", ".docx", ".txt"]
        ),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application :class:`Settings` singleton.

    Using ``lru_cache`` guarantees the environment is parsed only once per
    process while still allowing tests to bypass the cache via
    ``get_settings.cache_clear()`` if environment variables are mutated
    mid-test-run.
    """
    return _build_settings()
