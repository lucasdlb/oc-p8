"""Tests for monitoring.metrics module — verify metric definitions."""

from prometheus_client import Counter, Gauge, Histogram

from credit_risk_server.monitoring.metrics import (
    ACTIVE_REQUESTS,
    MODEL_LOADED,
    PREDICTION_DURATION,
    PREDICTIONS_TOTAL,
    REQUEST_LATENCY,
    REQUESTS_TOTAL,
)


class TestMetricsExist:
    def test_requests_total_is_counter(self):
        assert isinstance(REQUESTS_TOTAL, Counter)

    def test_request_latency_is_histogram(self):
        assert isinstance(REQUEST_LATENCY, Histogram)

    def test_active_requests_is_gauge(self):
        assert isinstance(ACTIVE_REQUESTS, Gauge)

    def test_predictions_total_is_counter(self):
        assert isinstance(PREDICTIONS_TOTAL, Counter)

    def test_prediction_duration_is_histogram(self):
        assert isinstance(PREDICTION_DURATION, Histogram)

    def test_model_loaded_is_gauge(self):
        assert isinstance(MODEL_LOADED, Gauge)


class TestMetricLabels:
    def test_requests_total_labels(self):
        assert "method" in REQUESTS_TOTAL._labelnames
        assert "endpoint" in REQUESTS_TOTAL._labelnames
        assert "status_code" in REQUESTS_TOTAL._labelnames

    def test_prediction_duration_labels(self):
        assert "endpoint" in PREDICTION_DURATION._labelnames

    def test_predictions_total_labels(self):
        assert "endpoint" in PREDICTIONS_TOTAL._labelnames
