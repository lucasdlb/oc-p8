"""Load InferencePipeline from disk.

This module has no dependency on config or FastAPI — it takes a ``Path``
and returns a ready-to-use ``InferencePipeline`` instance.
"""

from pathlib import Path

from credit_risk_models import InferencePipeline

from credit_risk_server.core.exceptions import ModelLoadError


def load_model(model_path: Path) -> InferencePipeline:
    """Load an InferencePipeline from a pickle file on disk.

    Args:
        model_path: Filesystem path to the pickled model.

    Returns:
        A deserialized ``InferencePipeline`` instance.

    Raises:
        ModelLoadError: If the file cannot be read or the object is invalid.
    """
    try:
        return InferencePipeline.load(model_path)
    except Exception as e:
        raise ModelLoadError(f"failed to load model from {model_path}: {e}") from e
