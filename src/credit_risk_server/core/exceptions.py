"""Custom exceptions — decoupled from FastAPI."""


class PredictionError(Exception):
    """Base exception for prediction-related errors."""


class InvalidInputError(PredictionError):
    """Raised when input data fails validation."""


class ModelLoadError(PredictionError):
    """Raised when the model cannot be loaded from disk."""
