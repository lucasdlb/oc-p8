"""PolarsDataSource — wraps a credit_risk_data loader for on-demand table access.

Calls loader.load() per request, applies SK_ID_CURR filtering via Polars predicate
pushdown, and collects only when needed. With PLLazyDataLoader, the filter propagates
through joins automatically — no manual FK resolution required.

Usage:
    from credit_risk_data import PLLazyDataLoader
    loader = PLLazyDataLoader(data_path=Path("data"), csv_names=SOURCE_CSV_NAME_MAP)
    source = PolarsDataSource.from_loader(loader)
    df = source.get_table("application", sk_ids={100001, 100002})
"""

from __future__ import annotations

import logging

import polars as pl
from credit_risk_data import BaseDataLoader

logger = logging.getLogger(__name__)


class PolarsDataSource:
    """Adapter over a BaseDataLoader — calls loader.load() per request.

    With PLLazyDataLoader, frames stay lazy until get_table() filters and collects,
    enabling predicate pushdown through joins.
    """

    def __init__(
        self,
        loader: BaseDataLoader,
        extra_columns: dict[str, list[str]] | None = None,
    ) -> None:
        self._loader = loader
        self._extra_columns = extra_columns or {}

    def get_table(self, name: str, sk_ids: set[int] | None = None) -> pl.DataFrame | None:
        try:
            frame = self._loader.load(name)
        except ValueError:
            logger.debug("table not available in loader", extra={"table": name})
            return None

        if sk_ids is not None:
            frame = frame.filter(pl.col("SK_ID_CURR").is_in(sk_ids))

        df = frame.collect() if isinstance(frame, pl.LazyFrame) else frame

        if df.is_empty():
            logger.debug(
                "table empty after filtering",
                extra={"table": name, "sk_ids_count": len(sk_ids or [])},
            )
            return None

        dropped = [c for c in self._extra_columns.get(name, []) if c in df.columns]
        if dropped:
            logger.debug("dropping extra columns", extra={"table": name, "columns": dropped})
            df = df.drop(dropped)

        logger.debug(
            "table loaded",
            extra={"table": name, "rows": df.height, "columns": len(df.columns)},
        )
        return df

    @classmethod
    def from_loader(
        cls,
        loader: BaseDataLoader,
        *,
        extra_columns: dict[str, list[str]] | None = None,
    ) -> PolarsDataSource:
        """Convenience constructor that auto-registers TARGET for stripping."""
        extras: dict[str, list[str]] = dict(extra_columns) if extra_columns else {}
        extras.setdefault("application", []).append("TARGET")
        return cls(loader, extra_columns=extras)
