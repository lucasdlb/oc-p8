"""Critical case tests — missing data, invalid types, outliers, empty tables."""

import polars as pl
import pytest
from pydantic import ValidationError

from credit_risk_server.api.schemas.application import ApplicationRow
from credit_risk_server.api.schemas.bureau import BureauRow
from credit_risk_server.api.schemas.prediction import PredictRequest
from credit_risk_server.core.exceptions import InvalidInputError, PredictionError
from credit_risk_server.models.predictor import predict, predict_from_tables
from tests.conftest import MINIMAL_APP_ROW


class TestMissingData:
    def test_null_on_required_int_field(self):
        data = {**MINIMAL_APP_ROW, "SK_ID_CURR": None}
        with pytest.raises(ValidationError):
            ApplicationRow(**data)

    def test_null_on_required_float_field(self):
        data = {**MINIMAL_APP_ROW, "AMT_CREDIT": None}
        with pytest.raises(ValidationError):
            ApplicationRow(**data)

    def test_null_on_required_str_field(self):
        data = {**MINIMAL_APP_ROW, "CODE_GENDER": None}
        with pytest.raises(ValidationError):
            ApplicationRow(**data)

    def test_missing_required_column_entirely(self):
        data = {k: v for k, v in MINIMAL_APP_ROW.items() if k != "AMT_CREDIT"}
        with pytest.raises(ValidationError, match="AMT_CREDIT"):
            ApplicationRow(**data)


class TestInvalidTypes:
    def test_string_where_int_expected(self):
        data = {**MINIMAL_APP_ROW, "CNT_CHILDREN": "three"}
        with pytest.raises(ValidationError):
            ApplicationRow(**data)

    def test_string_where_float_expected(self):
        data = {**MINIMAL_APP_ROW, "AMT_INCOME_TOTAL": "lots"}
        with pytest.raises(ValidationError):
            ApplicationRow(**data)

    def test_int_where_string_expected(self):
        data = {**MINIMAL_APP_ROW, "CODE_GENDER": 1}
        with pytest.raises(ValidationError):
            ApplicationRow(**data)

    def test_negative_sk_id_accepted(self):
        row = ApplicationRow(**{**MINIMAL_APP_ROW, "SK_ID_CURR": -1})
        assert row.SK_ID_CURR == -1

    def test_float_coerced_from_int(self):
        data = {**MINIMAL_APP_ROW, "AMT_CREDIT": 500000}
        row = ApplicationRow(**data)
        assert isinstance(row.AMT_CREDIT, float)


class TestOutliers:
    def test_very_large_int(self):
        data = {**MINIMAL_APP_ROW, "SK_ID_CURR": 999999999}
        row = ApplicationRow(**data)
        assert row.SK_ID_CURR == 999999999

    def test_very_large_float(self):
        data = {**MINIMAL_APP_ROW, "AMT_INCOME_TOTAL": 1e15}
        row = ApplicationRow(**data)
        assert row.AMT_INCOME_TOTAL == 1e15

    def test_negative_values_where_semantically_odd(self):
        data = {**MINIMAL_APP_ROW, "DAYS_BIRTH": -999999}
        row = ApplicationRow(**data)
        assert row.DAYS_BIRTH == -999999

    def test_zero_values(self):
        data = {**MINIMAL_APP_ROW, "AMT_INCOME_TOTAL": 0.0, "CNT_CHILDREN": 0}
        row = ApplicationRow(**data)
        assert row.AMT_INCOME_TOTAL == 0.0
        assert row.CNT_CHILDREN == 0


class TestEmptyTables:
    def test_empty_application_raises_invalid_input_predict(self):
        request = PredictRequest(application=[])
        model = object()
        with pytest.raises(InvalidInputError, match="application table must not be empty"):
            predict(model, request)  # ty: ignore[invalid-argument-type]

    def test_missing_application_in_raw_tables(self):
        from unittest.mock import MagicMock

        model = MagicMock()
        with pytest.raises(InvalidInputError, match="application"):
            predict_from_tables(model, {"bureau": pl.DataFrame()})

    def test_empty_dict_raises_invalid_input(self):
        from unittest.mock import MagicMock

        model = MagicMock()
        with pytest.raises(InvalidInputError, match="application"):
            predict_from_tables(model, {})


class TestBureauCriticalCases:
    def test_optional_null_accepted(self):
        row = BureauRow(
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
            AMT_ANNUITY=None,
            AMT_CREDIT_SUM=None,
            AMT_CREDIT_SUM_DEBT=None,
            DAYS_CREDIT_ENDDATE=None,
        )
        assert row.AMT_ANNUITY is None

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
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
                unknown_field=True,  # ty: ignore[unknown-argument]
            )


class TestModelFailure:
    def test_runtime_error_becomes_prediction_error(self):
        from unittest.mock import MagicMock

        from conftest import make_raw_tables

        model = MagicMock()
        model.predict.side_effect = RuntimeError("internal model failure")

        with pytest.raises(PredictionError, match="prediction failed"):
            predict_from_tables(model, make_raw_tables())

    def test_invalid_input_error_passes_through(self):
        from unittest.mock import MagicMock

        from conftest import make_raw_tables

        model = MagicMock()
        model.predict.side_effect = InvalidInputError("bad features")

        with pytest.raises(InvalidInputError, match="bad features"):
            predict_from_tables(model, make_raw_tables())
