"""Load InferencePipeline from disk.

This module has no dependency on config or FastAPI — it takes a ``Path``
and returns a ready-to-use ``InferencePipeline`` instance.
"""

import logging
from pathlib import Path

from credit_risk_models import InferencePipeline

from credit_risk_server.core.exceptions import ModelLoadError
from credit_risk_server.monitoring.metrics import MODEL_LOADED

logger = logging.getLogger(__name__)


def load_model(model_path: Path) -> InferencePipeline:
    """Load an InferencePipeline from a pickle file on disk.

    Args:
        model_path: Filesystem path to the pickled model.

    Returns:
        A deserialized ``InferencePipeline`` instance.

    Raises:
        ModelLoadError: If the file cannot be read or the object is invalid.
    """
    logger.info("loading model", extra={"model_path": str(model_path)})
    try:
        model = InferencePipeline.load(model_path)
    except Exception as e:
        MODEL_LOADED.set(0)
        logger.error("model load failed", extra={"model_path": str(model_path)})
        raise ModelLoadError(f"failed to load model from {model_path}: {e}") from e

    MODEL_LOADED.set(1)
    feature_count = len(model.feature_names)
    table_count = len(model.processing_pipelines)
    logger.info(
        "model loaded",
        extra={
            "model_path": str(model_path),
            "feature_count": feature_count,
            "table_count": table_count,
        },
    )
    return model
