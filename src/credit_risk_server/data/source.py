"""DataSource protocol — any source must implement this interface.

Adding a new source (DB, Parquet, API, …) = implement DataSource, nothing else changes.
"""

from typing import Protocol, runtime_checkable

import polars as pl

TABLE_NAMES = (
    "application",
    "bureau",
    "bureau_balance",
    "previous_application",
    "pos_cash_balance",
    "installments",
    "credit_card_balance",
)

SOURCE_CSV_NAME_MAP = {
    "application": "application_test.csv",
    "bureau": "bureau.csv",
    "bureau_balance": "bureau_balance.csv",
    "previous_application": "previous_application.csv",
    "pos_cash_balance": "POS_CASH_balance.csv",
    "installments": "installments_payments.csv",
    "credit_card_balance": "credit_card_balance.csv",
    "sample_submission": "sample_submission.csv",
}


@runtime_checkable
class DataSource(Protocol):
    """Return a Polars DataFrame for the requested table, or None if not available.

    Implementations are free to be lazy (query on demand) or eager (load all at init).
    The assembler calls each table name exactly once.

    When *sk_ids* is provided, only rows matching those SK_ID_CURR values are returned.
    For tables loaded via join (bureau_balance, etc.), SK_ID_CURR is available from the
    join and Polars pushes the filter through automatically.
    """

    def get_table(self, name: str, sk_ids: set[int] | None = None) -> pl.DataFrame | None:
        """Return the table filtered by *sk_ids*, or None if unavailable."""
        ...
