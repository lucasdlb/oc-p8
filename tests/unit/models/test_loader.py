"""Tests for models.loader module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from credit_risk_server.core.exceptions import ModelLoadError
from credit_risk_server.models.loader import load_model


class TestLoadModel:
    def test_load_model_success(self):
        mock_pipeline = MagicMock()
        mock_pipeline.feature_names = ["f1", "f2", "f3"]
        mock_pipeline.processing_pipelines = {"app": MagicMock()}

        with patch("credit_risk_server.models.loader.InferencePipeline") as MockPipeline:
            MockPipeline.load.return_value = mock_pipeline
            result = load_model(Path("/fake/model.pkl"))

        assert result is mock_pipeline

    def test_load_model_failure_raises_model_load_error(self):
        with patch("credit_risk_server.models.loader.InferencePipeline") as MockPipeline:
            MockPipeline.load.side_effect = FileNotFoundError("no file")
            with pytest.raises(ModelLoadError, match="failed to load model"):
                load_model(Path("/nonexistent/model.pkl"))

    def test_load_model_sets_model_loaded_gauge(self):
        mock_pipeline = MagicMock()
        mock_pipeline.feature_names = ["f1"]
        mock_pipeline.processing_pipelines = {}

        with patch("credit_risk_server.models.loader.InferencePipeline") as MockPipeline:
            MockPipeline.load.return_value = mock_pipeline
            with patch("credit_risk_server.models.loader.MODEL_LOADED") as mock_gauge:
                load_model(Path("/fake/model.pkl"))
                mock_gauge.set.assert_called_with(1)

    def test_load_model_sets_gauge_zero_on_failure(self):
        with patch("credit_risk_server.models.loader.InferencePipeline") as MockPipeline:
            MockPipeline.load.side_effect = RuntimeError("corrupt")
            with patch("credit_risk_server.models.loader.MODEL_LOADED") as mock_gauge:
                with pytest.raises(ModelLoadError):
                    load_model(Path("/bad/model.pkl"))
                mock_gauge.set.assert_called_with(0)
