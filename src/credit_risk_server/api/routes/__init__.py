"""API route routers."""

from credit_risk_server.api.routes.health import router as health_router
from credit_risk_server.api.routes.predict import router as predict_router

__all__ = ["health_router", "predict_router"]
