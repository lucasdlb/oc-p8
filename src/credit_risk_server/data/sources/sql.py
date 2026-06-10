"""SqlDataSource — loads tables from a SQL database via SQLAlchemy.

Swap this in when data moves from CSV to a relational DB (Postgres, etc.).
The assembler and predictor are unaffected — only the source changes.

Usage:
    source = SqlDataSource(
        engine=create_engine("postgresql+psycopg2://..."),
        schema_map={              # optional: override default table/column names
            "application": "application_train",
        },
    )
    df = source.get_table("application", sk_ids={100001, 100002})

Requirements (add to pyproject.toml [dependency-groups] when needed):
    sqlalchemy >= 2.0
    connectorx          # fast Polars <-> SQL bridge (optional but recommended)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import polars as pl

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine  # ty: ignore[unresolved-import]

_DEFAULT_TABLE_MAP: dict[str, str] = {
    "application": "application",
    "bureau": "bureau",
    "bureau_balance": "bureau_balance",
    "previous_application": "previous_application",
    "pos_cash_balance": "pos_cash_balance",
    "installments": "installments_payments",
    "credit_card_balance": "credit_card_balance",
}


class SqlDataSource:
    """Lazy DataSource backed by a SQLAlchemy engine.

    Tables are queried on demand (one SELECT per get_table call).
    bureau_balance requires a subquery through bureau — handled transparently.
    """

    def __init__(
        self,
        engine: Engine,
        schema_map: dict[str, str] | None = None,
    ) -> None:
        self._engine = engine
        self._table_map = {**_DEFAULT_TABLE_MAP, **(schema_map or {})}

    def get_table(self, name: str, sk_ids: set[int] | None = None) -> pl.DataFrame | None:
        logger.debug(
            "fetching table from sql",
            extra={"table": name, "sk_ids_count": len(sk_ids or [])},
        )
        if name == "bureau_balance":
            return self._fetch_bureau_balance(sk_ids)

        sql_table = self._table_map.get(name)
        if not sql_table:
            return None

        where = ""
        if sk_ids is not None:
            ids = ",".join(str(i) for i in sorted(sk_ids))
            where = f" WHERE SK_ID_CURR IN ({ids})"

        query = f"SELECT * FROM {sql_table}{where}"  # noqa: S608
        return self._read_sql(query)

    def _fetch_bureau_balance(self, sk_ids: set[int] | None = None) -> pl.DataFrame | None:
        bureau_table = self._table_map.get("bureau", "bureau")
        bb_table = self._table_map.get("bureau_balance", "bureau_balance")
        where = ""
        if sk_ids is not None:
            ids = ",".join(str(i) for i in sorted(sk_ids))
            where = f" WHERE b.SK_ID_CURR IN ({ids})"
        query = (
            f"SELECT bb.* FROM {bb_table} bb "  # noqa: S608
            f"JOIN {bureau_table} b ON bb.SK_ID_BUREAU = b.SK_ID_BUREAU"
            f"{where}"
        )
        return self._read_sql(query)

    def _read_sql(self, query: str) -> pl.DataFrame | None:
        """Execute *query* and return a Polars DataFrame.

        Tries connectorx first (faster), falls back to pandas bridge.
        """
        try:
            import connectorx as cx  # ty: ignore[unresolved-import]

            url = str(self._engine.url.render_as_string(hide_password=False))
            result = cx.read_sql(query, url, return_type="arrow")
            df = pl.from_arrow(result)
            df = df.to_frame() if isinstance(df, pl.Series) else df
            logger.debug("sql query via connectorx", extra={"rows": df.height})
            return df
        except ImportError:
            pass

        import pandas as pd

        with self._engine.connect() as conn:
            pdf = pd.read_sql(query, conn)
        return pl.from_pandas(pdf) if not pdf.empty else None
