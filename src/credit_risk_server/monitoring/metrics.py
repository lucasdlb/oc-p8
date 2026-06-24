"""Prometheus metrics — HTTP and business-level instrumentation.

All metrics are defined here so that any module can import what it needs
without coupling to the prometheus_client API directly.

Exposure is handled by ``start_http_server()`` in the FastAPI lifespan
(see ``api/main.py``) on a dedicated port (default 9100).
"""

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# HTTP metrics — used by the middleware in api/main.py
# ---------------------------------------------------------------------------

REQUESTS_TOTAL = Counter(
    "fastapi_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "fastapi_request_latency_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)

ACTIVE_REQUESTS = Gauge(
    "fastapi_active_requests",
    "Number of in-flight HTTP requests",
)

# ---------------------------------------------------------------------------
# Business metrics — used by predictor.py and loader.py
# ---------------------------------------------------------------------------

PREDICTIONS_TOTAL = Counter(
    "credit_risk_predictions_total",
    "Total number of successful scoring predictions",
    ["endpoint"],
)

PREDICTION_DURATION = Histogram(
    "credit_risk_prediction_duration_seconds",
    "Prediction latency in seconds",
    ["endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.25, 0.5, 1.0, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0),
)

MODEL_LOADED = Gauge(
    "credit_risk_model_loaded",
    "Whether the model is loaded (1 = loaded, 0 = not loaded)",
)
