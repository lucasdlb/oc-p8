"""Prediction logic — transforms raw tables into scores. No FastAPI dependency."""

import logging

import polars as pl
from credit_risk_models import InferencePipeline

from credit_risk_server.api.schemas.prediction import PredictRequest
from credit_risk_server.core.exceptions import InvalidInputError, PredictionError
from credit_risk_server.core.logging import Timer
from credit_risk_server.monitoring.drift import DriftMonitor
from credit_risk_server.monitoring.metrics import PREDICTION_DURATION, PREDICTIONS_TOTAL

logger = logging.getLogger(__name__)

TABLE_NAMES = (
    "application",
    "bureau",
    "bureau_balance",
    "previous_application",
    "pos_cash_balance",
    "installments",
    "credit_card_balance",
)


def _rows_to_dataframe(rows: list) -> pl.DataFrame:
    return pl.DataFrame([row.model_dump() for row in rows])


def _run(
    model: InferencePipeline,
    raw_tables: dict[str, pl.DataFrame],
    endpoint: str,
    monitor: DriftMonitor | None = None,
) -> list[tuple[int, float]]:
    """Shared backend — prediction with monitoring hooks."""
    table_info = {name: df.height for name, df in raw_tables.items()}
    logger.info("prediction started", extra={"tables": table_info, "endpoint": endpoint})

    with PREDICTION_DURATION.labels(endpoint=endpoint).time():
        with Timer(logger, "prediction", endpoint=endpoint):
            try:
                ids, probas = model.predict(raw_tables)
            except InvalidInputError:
                raise
            except Exception as exc:
                logger.error("prediction failed", extra={"tables": table_info}, exc_info=True)
                raise PredictionError(f"prediction failed: {exc}") from exc

    PREDICTIONS_TOTAL.labels(endpoint=endpoint).inc()
    results = list(zip(ids.tolist(), probas.tolist(), strict=True))

    if monitor is not None and "application" in raw_tables:
        app_rows = raw_tables["application"].to_dicts()
        for (_sk, proba), app_row in zip(results, app_rows, strict=False):
            monitor.record(float(proba), app_row)

    return results


def predict(
    model: InferencePipeline,
    request: PredictRequest,
    monitor: DriftMonitor | None = None,
) -> list[tuple[int, float]]:
    """HTTP row-oriented path — Pydantic validation → DataFrames → pipeline."""
    if not request.application:
        raise InvalidInputError("application table must not be empty")

    raw_tables: dict[str, pl.DataFrame] = {}

    for name in TABLE_NAMES:
        rows = getattr(request, name, None)
        if rows:
            raw_tables[name] = _rows_to_dataframe(rows)

    if "application" not in raw_tables:
        raise InvalidInputError("application table must not be empty")

    return _run(model, raw_tables, endpoint="predict_rows", monitor=monitor)


def predict_from_tables(
    model: InferencePipeline,
    raw_tables: dict[str, pl.DataFrame],
    monitor: DriftMonitor | None = None,
) -> list[tuple[int, float]]:
    """Internal path — DataFrames go straight to the pipeline."""
    if "application" not in raw_tables:
        raise InvalidInputError("application table must not be empty")

    return _run(model, raw_tables, endpoint="predict", monitor=monitor)
