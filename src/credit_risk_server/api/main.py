"""FastAPI application — app factory, lifespan, middleware, and exception handlers.

Creates the FastAPI app, registers routers, and wires up:

- **Lifespan**: initialises structured logging, loads the InferencePipeline
  into ``app.state.model``, and optionally creates the DataSource into
  ``app.state.data_source`` (when ``DATA_SOURCE`` is set). Both are cleared
  on shutdown.
- **Correlation middleware**: propagates or generates an ``X-Correlation-ID``
  request header through the entire request/response cycle and stores it
  in a :class:`~contextvars.ContextVar` so every log record is correlated.
- **Prometheus middleware**: increments request counters, observes latency,
  and tracks in-flight requests via gauges. Metrics are collected on a
  dedicated port (default 9100) managed by the lifespan.
- **Exception handlers**: map domain exceptions to HTTP status codes —

  ======== ===================== ========
  Handler  Exception             HTTP
  ======== ===================== ========
  422      InvalidInputError     Unprocessable Entity
  503      ModelLoadError        Service Unavailable
  500      PredictionError       Internal Server Error
  ======== ===================== ========
"""

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_client import start_http_server

from credit_risk_server.api.routes.health import router as health_router
from credit_risk_server.api.routes.predict import router as predict_router
from credit_risk_server.core.config import api_settings
from credit_risk_server.core.exceptions import InvalidInputError, ModelLoadError, PredictionError
from credit_risk_server.core.logging import correlation_id, setup_logging
from credit_risk_server.data.factory import make_source
from credit_risk_server.models.loader import load_model
from credit_risk_server.monitoring.drift import load_reference
from credit_risk_server.monitoring.metrics import (
    ACTIVE_REQUESTS,
    REQUEST_LATENCY,
    REQUESTS_TOTAL,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks.

    On startup:

    1. Configures structured JSON logging (idempotent).
    2. Starts the Prometheus metrics server on the configured port.
    3. Loads the :class:`~credit_risk_models.InferencePipeline` from disk
       and stores it on ``app.state.model``.
    4. Creates the :class:`~credit_risk_server.data.source.DataSource`
       from settings and stores it on ``app.state.data_source``.
    5. Loads the drift reference snapshot and creates an Evidently
       :class:`~credit_risk_server.monitoring.drift.DriftMonitor` on
       ``app.state.drift_monitor``; starts the periodic compute task
       when drift is enabled and a reference is found.

    On shutdown the drift task, metrics server, and all singletons are
    cleared to release resources.
    """
    server, t = start_http_server(api_settings.metrics_port)
    setup_logging(
        log_level=api_settings.log_level,
        env=api_settings.env,
        log_path=api_settings.log_path,
    )
    logger.info(
        "starting api",
        extra={"env": api_settings.env, "data_source": api_settings.data_source},
    )
    app.state.model = load_model(api_settings.model_path)
    logger.info("model loaded", extra={"model_path": str(api_settings.model_path)})
    app.state.data_source = make_source(api_settings)
    if app.state.data_source is not None:
        logger.info("data source ready", extra={"source_type": api_settings.data_source})
    else:
        logger.info("data source not configured — /predict endpoint disabled")

    monitor = load_reference(
        api_settings.drift_reference_path,
        api_settings.drift_workspace_path,
        buffer_size=api_settings.drift_buffer_size,
        min_samples=api_settings.drift_min_samples,
        psi_threshold=api_settings.drift_psi_threshold,
    )
    app.state.drift_monitor = monitor
    if monitor is not None and api_settings.drift_enabled:
        monitor.start_periodic_compute(interval_seconds=api_settings.drift_interval)
        logger.info(
            "drift monitoring started",
            extra={
                "interval": api_settings.drift_interval,
                "workspace": str(api_settings.drift_workspace_path),
            },
        )
    elif monitor is None:
        logger.info("drift monitoring disabled — no reference snapshot found")
    yield
    if monitor is not None:
        monitor.stop_periodic_compute()
    server.shutdown()
    server.server_close()
    t.join()
    app.state.model = None
    app.state.data_source = None
    app.state.drift_monitor = None
    logger.info("api shut down")


app = FastAPI(lifespan=lifespan)
app.include_router(predict_router)
app.include_router(health_router)


@app.middleware("http")
async def add_prometheus_metrics(request: Request, call_next):
    """Collect HTTP-level Prometheus metrics for every request."""
    method = request.method
    endpoint = request.url.path

    ACTIVE_REQUESTS.inc()
    with REQUEST_LATENCY.labels(method=method, endpoint=endpoint).time():
        response = await call_next(request)
    ACTIVE_REQUESTS.dec()

    REQUESTS_TOTAL.labels(
        method=method, endpoint=endpoint, status_code=str(response.status_code)
    ).inc()

    return response


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    """Propagate or generate an ``X-Correlation-ID`` for every request.

    If the incoming request already carries an ``X-Correlation-ID`` header it
    is reused; otherwise a new UUID is generated.  The value is stored in the
    :data:`~credit_risk_server.core.logging.correlation_id` context variable
    (injected into every log record) and echoed back in the response header.
    """
    corr = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    correlation_id.set(corr)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = corr
    return response


@app.exception_handler(InvalidInputError)
async def invalid_input_handler(request, exc):
    """Return 422 Unprocessable Entity for :class:`InvalidInputError`."""
    logger.warning("invalid input", extra={"detail": str(exc)})
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(ModelLoadError)
async def model_load_handler(request, exc):
    """Return 503 Service Unavailable for :class:`ModelLoadError`."""
    logger.error("model load error", extra={"detail": str(exc)})
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(PredictionError)
async def prediction_error_handler(request, exc):
    """Return 500 Internal Server Error for :class:`PredictionError`."""
    logger.error("prediction error", extra={"detail": str(exc)})
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Return 422 Unprocessable Entity for Pydantic validation errors."""
    logger.warning(
        "validation error",
        extra={"detail": exc.errors(), "endpoint": str(request.url.path)},
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    """Catch-all — log unexpected exceptions and return a structured 500."""
    logger.exception("unhandled exception", extra={"endpoint": str(request.url.path)})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
