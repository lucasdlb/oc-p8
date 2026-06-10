"""Pydantic model for the credit_card_balance table (23 columns)."""

from pydantic import BaseModel, ConfigDict


class CreditCardBalanceRow(BaseModel):
    """Credit card balance row (23 columns).

    Monthly balance snapshot for a previous credit card application,
    linked via ``SK_ID_PREV`` and ``SK_ID_CURR``.
    """

    model_config = ConfigDict(extra="forbid")

    SK_ID_PREV: int
    SK_ID_CURR: int
    MONTHS_BALANCE: int
    AMT_BALANCE: float
    AMT_CREDIT_LIMIT_ACTUAL: int
    AMT_DRAWINGS_ATM_CURRENT: float | None = None
    AMT_DRAWINGS_CURRENT: float
    AMT_DRAWINGS_OTHER_CURRENT: float | None = None
    AMT_DRAWINGS_POS_CURRENT: float | None = None
    AMT_INST_MIN_REGULARITY: float | None = None
    AMT_PAYMENT_CURRENT: float | None = None
    AMT_PAYMENT_TOTAL_CURRENT: float
    AMT_RECEIVABLE_PRINCIPAL: float
    AMT_RECIVABLE: float
    AMT_TOTAL_RECEIVABLE: float
    CNT_DRAWINGS_ATM_CURRENT: float | None = None
    CNT_DRAWINGS_CURRENT: int
    CNT_DRAWINGS_OTHER_CURRENT: float | None = None
    CNT_DRAWINGS_POS_CURRENT: float | None = None
    CNT_INSTALMENT_MATURE_CUM: float | None = None
    NAME_CONTRACT_STATUS: str
    SK_DPD: int
    SK_DPD_DEF: int
