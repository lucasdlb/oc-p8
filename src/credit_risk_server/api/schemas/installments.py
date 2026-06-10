"""Pydantic model for the installments_payments table (8 columns)."""

from pydantic import BaseModel, ConfigDict


class InstallmentRow(BaseModel):
    """Installments payments row (8 columns).

    One row per instalment payment on a previous credit, linked via
    ``SK_ID_PREV`` and ``SK_ID_CURR``.
    """

    model_config = ConfigDict(extra="forbid")

    SK_ID_PREV: int
    SK_ID_CURR: int
    NUM_INSTALMENT_VERSION: float
    NUM_INSTALMENT_NUMBER: int
    DAYS_INSTALMENT: float
    DAYS_ENTRY_PAYMENT: float | None = None
    AMT_INSTALMENT: float
    AMT_PAYMENT: float | None = None
