"""POST /predict — sk_ids → DataSource → InferencePipeline → scores.
POST /predict/rows — row-oriented PredictRequest → InferencePipeline → scores.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from credit_risk_server.api.dependencies import get_data_source, get_model
from credit_risk_server.api.schemas.prediction import (
    PredictFromSourceRequest,
    PredictRequest,
    PredictResponse,
)
from credit_risk_server.data.assembler import assemble
from credit_risk_server.data.source import DataSource
from credit_risk_server.models.predictor import predict, predict_from_tables

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/predict", response_model=list[PredictResponse])
def predict_from_source(
    request: PredictFromSourceRequest,
    model=Depends(get_model),  # noqa: B008
    source: DataSource | None = Depends(get_data_source),  # noqa: B008
) -> list[PredictResponse]:
    """Score clients by their ``SK_ID_CURR`` using data loaded from the configured source.

    Flow: ``sk_ids`` → :func:`~credit_risk_server.data.assembler.assemble`
    → :func:`~credit_risk_server.models.predictor.predict_from_tables` → response.

    Returns 503 when no data source is configured (DATA_SOURCE omitted).

    Args:
        request: JSON body containing the list of ``sk_ids`` to score.
        model: Inference pipeline singleton injected from ``app.state``.
        source: Data source singleton injected from ``app.state``.

    Returns:
        List of :class:`PredictResponse` with ``sk_id_curr`` and ``probability``.
    """
    if source is None:
        raise HTTPException(status_code=503, detail="No data source configured — set DATA_SOURCE")
    sk_ids = set(request.sk_ids)
    logger.info("predict request", extra={"sk_ids": list(sk_ids), "count": len(sk_ids)})
    raw_tables = assemble(source, sk_ids=sk_ids)
    results = predict_from_tables(model, raw_tables)
    logger.info("predict response", extra={"count": len(results)})
    return [PredictResponse(sk_id_curr=int(sk), probability=float(prob)) for sk, prob in results]


@router.post("/predict/rows", response_model=list[PredictResponse])
def predict_from_rows(
    request: PredictRequest,
    model=Depends(get_model),  # noqa: B008
) -> list[PredictResponse]:
    """Score clients from inline row data posted in the request body.

    The client provides the seven input tables as lists of row objects.
    Rows are converted to Polars DataFrames and fed directly to
    :func:`~credit_risk_server.models.predictor.predict`.

    Args:
        request: JSON body containing all table rows
            (``application`` is required; remaining tables are optional).
        model: Inference pipeline singleton injected from ``app.state``.

    Returns:
        List of :class:`PredictResponse` with ``sk_id_curr`` and ``probability``.
    """
    app_count = len(request.application)
    logger.info("predict/rows request", extra={"application_rows": app_count})
    results = predict(model, request)
    logger.info("predict/rows response", extra={"count": len(results)})
    return [PredictResponse(sk_id_curr=int(sk), probability=float(prob)) for sk, prob in results]
