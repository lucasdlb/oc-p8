"""Unit tests for predictor module — predict and predict_from_tables."""

from unittest.mock import MagicMock

import numpy as np
import polars as pl
import pytest

from credit_risk_server.api.schemas.prediction import PredictRequest
from credit_risk_server.core.exceptions import InvalidInputError, PredictionError
from credit_risk_server.models.predictor import predict, predict_from_tables
from tests.conftest import MINIMAL_APP_ROW, make_application_rows


def _make_model(ids=None, probas=None):
    """Create a mock InferencePipeline with configurable return values."""
    model = MagicMock()
    if ids is None:
        ids = np.array([100001])
    if probas is None:
        probas = np.array([0.42])
    model.predict.return_value = (ids, probas)
    return model


def _make_raw_tables(n=1, start_id=100001):
    """Build a dict with an application DataFrame."""
    rows = [{**MINIMAL_APP_ROW, "SK_ID_CURR": start_id + i} for i in range(n)]
    return {"application": pl.DataFrame(rows)}


# ---------------------------------------------------------------------------
# predict_from_tables
# ---------------------------------------------------------------------------


class TestPredictFromTables:
    def test_returns_list_of_tuples(self):
        model = _make_model(
            ids=np.array([100001, 100002]),
            probas=np.array([0.12, 0.87]),
        )
        result = predict_from_tables(model, _make_raw_tables(2, 100001))

        assert len(result) == 2
        assert result[0] == (100001, pytest.approx(0.12))
        assert result[1] == (100002, pytest.approx(0.87))

    def test_single_row(self):
        model = _make_model(ids=np.array([100001]), probas=np.array([0.5]))
        result = predict_from_tables(model, _make_raw_tables(1))

        assert len(result) == 1
        assert result[0] == (100001, pytest.approx(0.5))

    def test_raises_on_missing_application(self):
        model = _make_model()
        with pytest.raises(InvalidInputError, match="application"):
            predict_from_tables(model, {"bureau": pl.DataFrame()})

    def test_raises_on_empty_dict(self):
        model = _make_model()
        with pytest.raises(InvalidInputError, match="application"):
            predict_from_tables(model, {})

    def test_passes_tables_to_model(self):
        raw = _make_raw_tables()
        model = _make_model()
        predict_from_tables(model, raw)

        model.predict.assert_called_once_with(raw)

    def test_wraps_model_error_as_prediction_error(self):
        model = _make_model()
        model.predict.side_effect = RuntimeError("boom")

        with pytest.raises(PredictionError, match="prediction failed"):
            predict_from_tables(model, _make_raw_tables())

    def test_passes_invalid_input_error_through(self):
        model = _make_model()
        model.predict.side_effect = InvalidInputError("bad input")

        with pytest.raises(InvalidInputError, match="bad input"):
            predict_from_tables(model, _make_raw_tables())


# ---------------------------------------------------------------------------
# predict (row-oriented path)
# ---------------------------------------------------------------------------


class TestPredict:
    def test_converts_rows_to_dataframes(self):
        app_rows = make_application_rows(2, 100001)
        request = PredictRequest(application=app_rows)

        model = _make_model(
            ids=np.array([100001, 100002]),
            probas=np.array([0.1, 0.9]),
        )
        result = predict(model, request)

        assert len(result) == 2
        assert result[0][0] == 100001
        assert result[1][0] == 100002

    def test_optional_tables_included(self):
        from credit_risk_server.api.schemas.bureau import BureauRow

        app_rows = make_application_rows(1, 100001)
        bureau_rows = [
            BureauRow(
                SK_ID_CURR=100001,
                SK_ID_BUREAU=5000001,
                CREDIT_ACTIVE="Closed",
                CREDIT_CURRENCY="currency 1",
                DAYS_CREDIT=-100,
                CREDIT_DAY_OVERDUE=0,
                CNT_CREDIT_PROLONG=0,
                AMT_CREDIT_SUM_OVERDUE=0.0,
                CREDIT_TYPE="Consumer credit",
                DAYS_CREDIT_UPDATE=-50,
            ),
        ]
        request = PredictRequest(application=app_rows, bureau=bureau_rows)

        model = _make_model(ids=np.array([100001]), probas=np.array([0.3]))
        result = predict(model, request)

        assert len(result) == 1
        call_args = model.predict.call_args[0][0]
        assert "application" in call_args
        assert "bureau" in call_args

    def test_raises_on_empty_application(self):
        request = PredictRequest(application=[])
        model = _make_model()

        with pytest.raises(InvalidInputError, match="application table must not be empty"):
            predict(model, request)

    def test_wraps_model_error(self):
        app_rows = make_application_rows(1)
        request = PredictRequest(application=app_rows)

        model = _make_model()
        model.predict.side_effect = RuntimeError("fail")

        with pytest.raises(PredictionError, match="prediction failed"):
            predict(model, request)
