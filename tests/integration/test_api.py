"""Integration tests for FastAPI endpoints — TestClient with mocked model and data source."""

from unittest.mock import MagicMock

import numpy as np
import polars as pl
import pytest

from credit_risk_server.data.source import DataSource
from tests.conftest import MINIMAL_APP_ROW, _make_test_app, make_mock_model


class TestHealthEndpoint:
    def test_health_model_loaded(self):
        model = make_mock_model()
        test_app = _make_test_app(model=model, data_source=None)
        from fastapi.testclient import TestClient

        with TestClient(test_app) as client:
            response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["model_loaded"] is True

    def test_health_model_not_loaded(self):
        test_app = _make_test_app(model=None, data_source=None)
        from fastapi.testclient import TestClient

        with TestClient(test_app) as client:
            response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["model_loaded"] is False


class TestPredictRowsEndpoint:
    def test_predict_rows_basic(self):
        model = make_mock_model(
            ids=np.array([100001]),
            probas=np.array([0.42]),
        )
        test_app = _make_test_app(model=model, data_source=None)
        payload = {"application": [MINIMAL_APP_ROW]}

        from fastapi.testclient import TestClient

        with TestClient(test_app) as client:
            response = client.post("/predict/rows", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["sk_id_curr"] == 100001
        assert data[0]["probability"] == pytest.approx(0.42, abs=1e-6)

    def test_predict_rows_multiple(self):
        model = make_mock_model(
            ids=np.array([100001, 100002]),
            probas=np.array([0.12, 0.87]),
        )
        test_app = _make_test_app(model=model, data_source=None)

        second_row = {**MINIMAL_APP_ROW, "SK_ID_CURR": 100002}
        payload = {"application": [MINIMAL_APP_ROW, second_row]}

        from fastapi.testclient import TestClient

        with TestClient(test_app) as client:
            response = client.post("/predict/rows", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_predict_rows_with_optional_bureau(self):
        model = make_mock_model(
            ids=np.array([100001]),
            probas=np.array([0.3]),
        )
        test_app = _make_test_app(model=model, data_source=None)

        payload = {
            "application": [MINIMAL_APP_ROW],
            "bureau": [
                {
                    "SK_ID_CURR": 100001,
                    "SK_ID_BUREAU": 5000001,
                    "CREDIT_ACTIVE": "Closed",
                    "CREDIT_CURRENCY": "currency 1",
                    "DAYS_CREDIT": -100,
                    "CREDIT_DAY_OVERDUE": 0,
                    "CNT_CREDIT_PROLONG": 0,
                    "AMT_CREDIT_SUM_OVERDUE": 0.0,
                    "CREDIT_TYPE": "Consumer credit",
                    "DAYS_CREDIT_UPDATE": -50,
                },
            ],
        }

        from fastapi.testclient import TestClient

        with TestClient(test_app) as client:
            response = client.post("/predict/rows", json=payload)

        assert response.status_code == 200

    def test_predict_rows_empty_application_returns_422(self):
        model = make_mock_model()
        test_app = _make_test_app(model=model, data_source=None)

        from fastapi.testclient import TestClient

        with TestClient(test_app) as client:
            response = client.post("/predict/rows", json={"application": []})

        assert response.status_code == 422

    def test_predict_rows_invalid_input_returns_422(self):
        model = make_mock_model()
        test_app = _make_test_app(model=model, data_source=None)

        from fastapi.testclient import TestClient

        with TestClient(test_app) as client:
            response = client.post(
                "/predict/rows", json={"application": [{"SK_ID_CURR": "not_a_number"}]}
            )

        assert response.status_code == 422

    def test_predict_rows_extra_field_returns_422(self):
        model = make_mock_model()
        test_app = _make_test_app(model=model, data_source=None)

        from fastapi.testclient import TestClient

        with TestClient(test_app) as client:
            response = client.post(
                "/predict/rows", json={"application": [MINIMAL_APP_ROW], "unknown_table": []}
            )

        assert response.status_code == 422


class TestPredictEndpoint:
    def test_predict_no_data_source_returns_503(self):
        model = make_mock_model()
        test_app = _make_test_app(model=model, data_source=None)

        from fastapi.testclient import TestClient

        with TestClient(test_app) as client:
            response = client.post("/predict", json={"sk_ids": [100001]})

        assert response.status_code == 503

    def test_predict_with_data_source(self):
        model = make_mock_model(
            ids=np.array([100001]),
            probas=np.array([0.42]),
        )
        source = MagicMock(spec=DataSource)
        source.get_table.return_value = pl.DataFrame([MINIMAL_APP_ROW])
        test_app = _make_test_app(model=model, data_source=source)

        from fastapi.testclient import TestClient

        with TestClient(test_app) as client:
            response = client.post("/predict", json={"sk_ids": [100001]})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["sk_id_curr"] == 100001

    def test_predict_empty_sk_ids_returns_422(self):
        model = make_mock_model()
        test_app = _make_test_app(model=model, data_source=None)

        from fastapi.testclient import TestClient

        with TestClient(test_app) as client:
            response = client.post("/predict", json={"sk_ids": []})

        assert response.status_code == 422


class TestExceptionHandlers:
    def test_invalid_input_returns_422(self):
        from credit_risk_server.core.exceptions import InvalidInputError

        model = MagicMock()
        model.predict.side_effect = InvalidInputError("bad input")
        test_app = _make_test_app(model=model, data_source=None)

        payload = {"application": [MINIMAL_APP_ROW]}

        from fastapi.testclient import TestClient

        with TestClient(test_app) as client:
            response = client.post("/predict/rows", json=payload)

        assert response.status_code == 422

    def test_prediction_error_returns_500(self):
        from credit_risk_server.core.exceptions import PredictionError

        model = MagicMock()
        model.predict.side_effect = PredictionError("internal failure")
        test_app = _make_test_app(model=model, data_source=None)

        payload = {"application": [MINIMAL_APP_ROW]}

        from fastapi.testclient import TestClient

        with TestClient(test_app) as client:
            response = client.post("/predict/rows", json=payload)

        assert response.status_code == 500
