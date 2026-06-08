"""Model loading singleton — load InferencePipeline once at startup."""

from credit_risk_models import InferencePipeline
from fastapi import Request


def get_model(request: Request) -> InferencePipeline:
    """FastAPI dependency that returns the model loaded during app lifespan."""
    return request.app.state.model
