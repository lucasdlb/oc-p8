"""GET /health — health check endpoint."""

import logging

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
def health_check(request: Request) -> dict:
    """Return service health and model availability.

    Response::

        {"status": "ok", "model_loaded": true|false}

    Useful for liveness probes and operational dashboards.
    """
    model_loaded = request.app.state.model is not None
    logger.debug("health check", extra={"model_loaded": model_loaded})
    return {
        "status": "ok",
        "model_loaded": model_loaded,
    }
