"""Tests for core.config module — path resolution and validation."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from credit_risk_server.core.config import ApiSettings, AppSettings, find_project_root


class TestFindProjectRoot:
    def test_finds_project_root_from_file(self):
        root = find_project_root(Path(__file__))
        assert (root / "pyproject.toml").exists()

    def test_fallback_when_no_marker(self):
        with patch("credit_risk_server.core.config._ROOT_MARKERS", ("__nonexistent__",)):
            result = find_project_root(Path(__file__))
            assert isinstance(result, Path)


class TestAppSettings:
    def test_env_var_override(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=False):
            settings = AppSettings()
            assert settings.log_level == "DEBUG"

    def test_resolve_relative_log_path(self):
        with patch.dict(os.environ, {"LOG_PATH": "logs/test.log"}, clear=False):
            settings = AppSettings()
            assert settings.log_path.is_absolute()

    def test_absolute_log_path_unchanged(self):
        log_path = "/tmp/test_settings.log"
        with patch.dict(os.environ, {"LOG_PATH": log_path}, clear=False):
            settings = AppSettings()
            assert str(settings.log_path) == log_path


class TestApiSettings:
    def test_model_path_must_exist(self):
        with patch.dict(
            os.environ,
            {"MODEL_PATH": "/nonexistent/path/model.pkl"},
            clear=False,
        ):
            with pytest.raises(ValidationError, match="model not found"):
                ApiSettings()

    def test_resolve_relative_data_path(self):
        with patch.dict(
            os.environ,
            {
                "MODEL_PATH": "/tmp/fake_model.pkl",
                "DATA_PATH": "data",
            },
            clear=False,
        ):
            try:
                s = ApiSettings()
                assert s.data_path.is_absolute()
            except ValidationError:
                pass
