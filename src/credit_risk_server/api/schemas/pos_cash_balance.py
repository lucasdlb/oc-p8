"""Pydantic model for the POS_CASH_balance table (8 columns)."""

from pydantic import BaseModel, ConfigDict


class PosCashBalanceRow(BaseModel):
    """POS/CASH balance row (8 columns).

    Monthly balance snapshot for a previous point-of-sale or cash loan,
    linked via ``SK_ID_PREV`` and ``SK_ID_CURR``.
    """

    model_config = ConfigDict(extra="forbid")

    SK_ID_PREV: int
    SK_ID_CURR: int
    MONTHS_BALANCE: int
    CNT_INSTALMENT: float | None = None
    CNT_INSTALMENT_FUTURE: float | None = None
    NAME_CONTRACT_STATUS: str
    SK_DPD: int
    SK_DPD_DEF: int
