"""Application settings loaded from environment variables via pydantic-settings.

Each service gets its own Settings class with its own ``.env.<service>`` file.
``AppSettings`` provides shared fields (log_level, env, log_path) that subclasses
inherit.

Relative paths in env files are resolved against the project root (the directory
containing ``pyproject.toml``), so the app works regardless of the working directory.
"""

from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_MARKERS = ("pyproject.toml", ".git", ".gitignore")


def find_project_root(start: Path | None = None, markers: tuple[str, ...] = _ROOT_MARKERS) -> Path:
    """Walk upward from *start* until a directory containing any of *markers* is found.

    Falls back to ``start`` itself if no marker is found (e.g. inside a container).
    """
    current = (start or Path(__file__)).resolve()
    for parent in current.parents:
        if any((parent / marker).exists() for marker in markers):
            return parent
    return current


PROJECT_ROOT = find_project_root()


class AppSettings(BaseSettings):
    """Fields shared across all services."""

    log_level: str = "INFO"
    log_path: Path = Path("logs/app.log")
    env: Literal["dev", "prod"] = "dev"

    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env"), extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def resolve_relative_paths(cls, values: dict) -> dict:
        """Turn relative paths into absolute paths rooted at the project directory."""
        for key in ("log_path",):
            raw = values.get(key)
            if raw is None:
                continue
            path = Path(raw)
            if not path.is_absolute():
                values[key] = str(PROJECT_ROOT / path)
        return values


class ApiSettings(AppSettings):
    """API service configuration — loaded from ``.env.api``."""

    model_path: Path
    elasticsearch_url: str
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    metrics_port: int = 9090
    data_source: Literal["csv", "sql"] | None = "csv"
    data_path: Path = Path("data")

    model_config = SettingsConfigDict(env_file=str(PROJECT_ROOT / ".env.api"), extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def resolve_relative_paths(cls, values: dict) -> dict:
        """Turn relative paths into absolute paths rooted at the project directory."""
        for key in ("model_path", "data_path"):
            raw = values.get(key)
            if raw is None:
                continue
            path = Path(raw)
            if not path.is_absolute():
                values[key] = str(PROJECT_ROOT / path)
        return values

    @field_validator("model_path")
    @classmethod
    def model_must_exist(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"model not found: {v} (project root: {PROJECT_ROOT})")
        return v


api_settings = ApiSettings()  # ty: ignore[missing-argument]
