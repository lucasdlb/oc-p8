"""Tests for api.dependencies module."""

from unittest.mock import MagicMock

from credit_risk_server.api.dependencies import get_data_source, get_model
from credit_risk_server.data.source import DataSource


class TestGetModel:
    def test_returns_model_from_app_state(self):
        from fastapi import Request

        mock_model = MagicMock()
        app = MagicMock()
        app.state.model = mock_model
        request = MagicMock(spec=Request)
        request.app = app

        result = get_model(request)
        assert result is mock_model


class TestGetDataSource:
    def test_returns_data_source_from_app_state(self):
        from fastapi import Request

        mock_source = MagicMock(spec=DataSource)
        app = MagicMock()
        app.state.data_source = mock_source
        request = MagicMock(spec=Request)
        request.app = app

        result = get_data_source(request)
        assert result is mock_source

    def test_returns_none_when_no_data_source(self):
        from fastapi import Request

        app = MagicMock()
        app.state.data_source = None
        request = MagicMock(spec=Request)
        request.app = app

        result = get_data_source(request)
        assert result is None
