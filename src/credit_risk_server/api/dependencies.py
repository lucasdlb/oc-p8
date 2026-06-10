"""FastAPI dependency injection — model and data source singletons."""

from credit_risk_models import InferencePipeline
from fastapi import Request

from credit_risk_server.data.source import DataSource


def get_model(request: Request) -> InferencePipeline:
    """Return the :class:`~credit_risk_models.InferencePipeline` singleton.

    Stored on ``app.state.model`` during the application lifespan.
    Injected via ``Depends(get_model)`` in route handlers so the
    inference pipeline is available without global state.
    """
    return request.app.state.model


def get_data_source(request: Request) -> DataSource | None:
    """Return the :class:`~credit_risk_server.data.source.DataSource` singleton.

    Returns None when no data source is configured (DATA_SOURCE omitted).
    Routes that require a source should check for None and raise 503.
    """
    return request.app.state.data_source
