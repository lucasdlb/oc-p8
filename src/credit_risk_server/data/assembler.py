"""Assembler — converts a DataSource into raw tables for batch prediction."""

import logging

import polars as pl

from credit_risk_server.core.exceptions import InvalidInputError
from credit_risk_server.data.source import TABLE_NAMES, DataSource

logger = logging.getLogger(__name__)


def assemble(source: DataSource, sk_ids: set[int]) -> dict[str, pl.DataFrame]:
    """Pull tables from *source* filtered by *sk_ids* and return raw DataFrames.

    Filters all tables by SK_ID_CURR. With Polars lazy evaluation and PLLazyDataLoader,
    the filter pushes through joins automatically (bureau_balance, etc.).
    """
    logger.info("assembling tables", extra={"sk_ids_count": len(sk_ids)})
    tables: dict[str, pl.DataFrame] = {}
    for name in TABLE_NAMES:
        df = source.get_table(name, sk_ids=sk_ids)
        if df is not None and not df.is_empty():
            tables[name] = df
            logger.debug("table assembled", extra={"table": name, "rows": df.height})

    if "application" not in tables:
        raise InvalidInputError("application table must not be empty for the given sk_ids")

    logger.info(
        "tables assembled",
        extra={"tables": list(tables.keys()), "sk_ids_count": len(sk_ids)},
    )
    return tables
