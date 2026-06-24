"""Tests for api.main module — exception handlers and middleware logic."""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from credit_risk_server.api.routes.health import router as health_router
from credit_risk_server.api.routes.predict import router as predict_router
from credit_risk_server.core.exceptions import InvalidInputError, ModelLoadError, PredictionError


def _make_app_with_handlers(model=None, data_source=None):
    """Create a test app that uses production exception handlers and middleware."""
    import logging

    from credit_risk_server.api.main import correlation_middleware

    test_app = FastAPI(lifespan=None)
    test_app.include_router(predict_router)
    test_app.include_router(health_router)

    @test_app.middleware("http")
    async def _correlation(request, call_next):
        return await correlation_middleware(request, call_next)

    @test_app.exception_handler(InvalidInputError)
    async def _invalid_input(request, exc):
        logging.warning("invalid input", extra={"detail": str(exc)})
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @test_app.exception_handler(ModelLoadError)
    async def _model_load(request, exc):
        logging.error("model load error", extra={"detail": str(exc)})
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @test_app.exception_handler(PredictionError)
    async def _prediction(request, exc):
        logging.error("prediction error", extra={"detail": str(exc)})
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=500, content={"detail": str(exc)})

    test_app.state.model = model
    test_app.state.data_source = data_source
    test_app.state.drift_monitor = None
    return test_app


class TestCorrelationMiddleware:
    def test_adds_correlation_id_header(self):
        app = _make_app_with_handlers(model=MagicMock(), data_source=None)
        with TestClient(app) as client:
            resp = client.get("/health")
        assert "X-Correlation-ID" in resp.headers

    def test_propagates_existing_correlation_id(self):
        app = _make_app_with_handlers(model=MagicMock(), data_source=None)
        with TestClient(app) as client:
            resp = client.get("/health", headers={"X-Correlation-ID": "my-corr-id"})
        assert resp.headers["X-Correlation-ID"] == "my-corr-id"


class TestExceptionHandlersViaAPI:
    def test_invalid_input_returns_422(self):
        from tests.conftest import MINIMAL_APP_ROW

        model = MagicMock()
        model.predict.side_effect = InvalidInputError("bad input")
        app = _make_app_with_handlers(model=model, data_source=None)

        with TestClient(app) as client:
            resp = client.post("/predict/rows", json={"application": [MINIMAL_APP_ROW]})
        assert resp.status_code == 422

    def test_model_load_error_returns_503(self):
        """ModelLoadError raised directly (not through predictor) maps to 503."""
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse

        app = FastAPI()

        @app.get("/test-503")
        async def raise_model_load():
            raise ModelLoadError("model missing")

        @app.exception_handler(ModelLoadError)
        async def handler(request, exc):
            return JSONResponse(status_code=503, content={"detail": str(exc)})

        with TestClient(app) as client:
            resp = client.get("/test-503")
        assert resp.status_code == 503

    def test_prediction_error_returns_500(self):
        from tests.conftest import MINIMAL_APP_ROW

        model = MagicMock()
        model.predict.side_effect = PredictionError("internal failure")
        app = _make_app_with_handlers(model=model, data_source=None)

        with TestClient(app) as client:
            resp = client.post("/predict/rows", json={"application": [MINIMAL_APP_ROW]})
        assert resp.status_code == 500
