"""Tests for core.exceptions module."""

from credit_risk_server.core.exceptions import InvalidInputError, ModelLoadError, PredictionError


def test_prediction_error_is_exception():
    assert issubclass(PredictionError, Exception)


def test_invalid_input_error_is_prediction_error():
    assert issubclass(InvalidInputError, PredictionError)


def test_model_load_error_is_prediction_error():
    assert issubclass(ModelLoadError, PredictionError)


def test_prediction_error_message():
    exc = PredictionError("test message")
    assert str(exc) == "test message"


def test_invalid_input_error_message():
    exc = InvalidInputError("bad input")
    assert str(exc) == "bad input"


def test_model_load_error_message():
    exc = ModelLoadError("model not found")
    assert str(exc) == "model not found"
