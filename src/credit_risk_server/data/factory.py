"""Factory — creates a DataSource from ApiSettings."""

import logging

from credit_risk_data import PLLazyDataLoader

from credit_risk_server.core.config import ApiSettings
from credit_risk_server.data.source import SOURCE_CSV_NAME_MAP, DataSource
from credit_risk_server.data.sources.polars import PolarsDataSource

logger = logging.getLogger(__name__)


def make_source(settings: ApiSettings) -> DataSource | None:
    """Create a DataSource based on the configured data_source type.

    Returns None when ``settings.data_source`` is None (source disabled).
    """
    if settings.data_source is None:
        logger.info("data source disabled — /predict endpoint will be unavailable")
        return None

    logger.info("creating data source", extra={"source_type": settings.data_source})
    match settings.data_source:
        case "csv":
            loader = PLLazyDataLoader(
                data_path=settings.data_path,
                csv_names=SOURCE_CSV_NAME_MAP,
            )
            source = PolarsDataSource.from_loader(loader)
            logger.info(
                "data source created",
                extra={"source_type": "csv", "data_path": str(settings.data_path)},
            )
            return source
        case "sql":
            raise NotImplementedError("SQL data source not yet configured")
        case _:
            raise ValueError(f"Unknown data source: {settings.data_source}")
