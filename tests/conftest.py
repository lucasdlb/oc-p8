"""Shared fixtures for pytest."""

from unittest.mock import MagicMock

import numpy as np
import polars as pl
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from credit_risk_server.api.schemas.application import ApplicationRow
from credit_risk_server.core.exceptions import InvalidInputError, ModelLoadError, PredictionError

MINIMAL_APP_ROW = {
    "SK_ID_CURR": 100001,
    "NAME_CONTRACT_TYPE": "Cash loans",
    "CODE_GENDER": "F",
    "FLAG_OWN_CAR": "N",
    "FLAG_OWN_REALTY": "Y",
    "CNT_CHILDREN": 0,
    "AMT_INCOME_TOTAL": 202500.0,
    "AMT_CREDIT": 500000.0,
    "AMT_GOODS_PRICE": 450000.0,
    "NAME_INCOME_TYPE": "Working",
    "NAME_EDUCATION_TYPE": "Secondary / secondary special",
    "NAME_FAMILY_STATUS": "Civil marriage",
    "NAME_HOUSING_TYPE": "House / apartment",
    "REGION_POPULATION_RELATIVE": 0.01885,
    "DAYS_BIRTH": -16765,
    "DAYS_EMPLOYED": -5643,
    "DAYS_REGISTRATION": -364.0,
    "DAYS_ID_PUBLISH": -4291,
    "FLAG_MOBIL": 1,
    "FLAG_EMP_PHONE": 1,
    "FLAG_WORK_PHONE": 0,
    "FLAG_CONT_MOBILE": 1,
    "FLAG_PHONE": 0,
    "FLAG_EMAIL": 0,
    "CNT_FAM_MEMBERS": 2.0,
    "REGION_RATING_CLIENT": 2,
    "REGION_RATING_CLIENT_W_CITY": 2,
    "WEEKDAY_APPR_PROCESS_START": "WEDNESDAY",
    "HOUR_APPR_PROCESS_START": 12,
    "REG_REGION_NOT_LIVE_REGION": 0,
    "REG_REGION_NOT_WORK_REGION": 0,
    "LIVE_REGION_NOT_WORK_REGION": 0,
    "REG_CITY_NOT_LIVE_CITY": 0,
    "REG_CITY_NOT_WORK_CITY": 0,
    "LIVE_CITY_NOT_WORK_CITY": 0,
    "ORGANIZATION_TYPE": "Business Entity Type 3",
    "DAYS_LAST_PHONE_CHANGE": -1134.0,
    "FLAG_DOCUMENT_2": 0,
    "FLAG_DOCUMENT_3": 1,
    "FLAG_DOCUMENT_4": 0,
    "FLAG_DOCUMENT_5": 0,
    "FLAG_DOCUMENT_6": 0,
    "FLAG_DOCUMENT_7": 0,
    "FLAG_DOCUMENT_8": 0,
    "FLAG_DOCUMENT_9": 0,
    "FLAG_DOCUMENT_10": 0,
    "FLAG_DOCUMENT_11": 0,
    "FLAG_DOCUMENT_12": 0,
    "FLAG_DOCUMENT_13": 0,
    "FLAG_DOCUMENT_14": 0,
    "FLAG_DOCUMENT_15": 0,
    "FLAG_DOCUMENT_16": 0,
    "FLAG_DOCUMENT_17": 0,
    "FLAG_DOCUMENT_18": 0,
    "FLAG_DOCUMENT_19": 0,
    "FLAG_DOCUMENT_20": 0,
    "FLAG_DOCUMENT_21": 0,
}

MINIMAL_BUREAU_ROW = {
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
}


def make_mock_model(ids=None, probas=None):
    """Return a mock InferencePipeline that returns deterministic predictions."""
    model = MagicMock()
    if ids is None:
        ids = np.array([100001])
    if probas is None:
        probas = np.array([0.42])
    model.predict.return_value = (ids, probas)
    return model


def make_application_df(n_rows: int = 1, start_id: int = 100001) -> pl.DataFrame:
    """Build a minimal application DataFrame with *n_rows* rows."""
    rows = []
    for i in range(n_rows):
        row = {**MINIMAL_APP_ROW, "SK_ID_CURR": start_id + i}
        rows.append(row)
    return pl.DataFrame(rows)


def make_application_rows(n_rows: int = 1, start_id: int = 100001) -> list[ApplicationRow]:
    """Build a list of ApplicationRow pydantic models."""
    rows = []
    for i in range(n_rows):
        row = {**MINIMAL_APP_ROW, "SK_ID_CURR": start_id + i}
        rows.append(ApplicationRow(**row))
    return rows


def make_raw_tables(n_rows: int = 1, start_id: int = 100001) -> dict[str, pl.DataFrame]:
    """Build raw_tables dict suitable for predict_from_tables."""
    return {"application": make_application_df(n_rows, start_id)}


def _make_test_app(model=None, data_source=None):
    """Create a FastAPI app for testing — reuses production handlers and middleware."""
    import uuid

    from fastapi import Request

    from credit_risk_server.api.routes.health import router as health_router
    from credit_risk_server.api.routes.predict import router as predict_router
    from credit_risk_server.core.logging import correlation_id

    test_app = FastAPI(lifespan=None)
    test_app.include_router(predict_router)
    test_app.include_router(health_router)

    @test_app.middleware("http")
    async def test_correlation_middleware(request: Request, call_next):
        corr = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        correlation_id.set(corr)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr
        return response

    test_app.add_exception_handler(InvalidInputError, _invalid_input_handler)
    test_app.add_exception_handler(ModelLoadError, _model_load_handler)
    test_app.add_exception_handler(PredictionError, _prediction_error_handler)

    test_app.state.model = model
    test_app.state.data_source = data_source
    test_app.state.drift_monitor = None
    return test_app


@pytest.fixture()
def mock_model():
    """Pytest fixture that provides a mock InferencePipeline."""
    return make_mock_model()


@pytest.fixture()
def client(mock_model):
    """FastAPI TestClient with model injected, no data source, no lifespan."""
    test_app = _make_test_app(model=mock_model, data_source=None)
    with TestClient(test_app) as c:
        yield c


async def _invalid_input_handler(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=422, content={"detail": str(exc)})


async def _model_load_handler(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=503, content={"detail": str(exc)})


async def _prediction_error_handler(request, exc):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=500, content={"detail": str(exc)})
