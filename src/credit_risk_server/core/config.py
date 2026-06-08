"""Application settings loaded from environment variables via pydantic-settings.

Each service gets its own Settings class with its own ``.env.<service>`` file.
``AppSettings`` provides shared fields (log_level, env) that subclasses inherit.
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Fields shared across all services."""

    log_level: str = "INFO"
    env: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class ApiSettings(AppSettings):
    """API service configuration — loaded from ``.env.api``."""

    model_path: Path
    elasticsearch_url: str
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    metrics_port: int = 9090

    model_config = SettingsConfigDict(env_file=".env.api", extra="ignore")

    @field_validator("model_path")
    @classmethod
    def model_must_exist(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"model not found: {v}")
        return v


api_settings = ApiSettings()  # ty: ignore[missing-argument]
