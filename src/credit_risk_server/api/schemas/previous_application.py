"""Pydantic model for the previous_application table (37 columns)."""

from pydantic import BaseModel, ConfigDict


class PreviousApplicationRow(BaseModel):
    """Previous application row (37 columns).

    One row per previous loan application made by the same client,
    linked via ``SK_ID_PREV`` and ``SK_ID_CURR``.
    """

    model_config = ConfigDict(extra="forbid")

    SK_ID_PREV: int
    SK_ID_CURR: int
    NAME_CONTRACT_TYPE: str
    AMT_ANNUITY: float | None = None
    AMT_APPLICATION: float
    AMT_CREDIT: float | None = None
    AMT_DOWN_PAYMENT: float | None = None
    AMT_GOODS_PRICE: float | None = None
    WEEKDAY_APPR_PROCESS_START: str
    HOUR_APPR_PROCESS_START: int
    FLAG_LAST_APPL_PER_CONTRACT: str
    NFLAG_LAST_APPL_IN_DAY: int
    RATE_DOWN_PAYMENT: float | None = None
    RATE_INTEREST_PRIMARY: float | None = None
    RATE_INTEREST_PRIVILEGED: float | None = None
    NAME_CASH_LOAN_PURPOSE: str
    NAME_CONTRACT_STATUS: str
    DAYS_DECISION: int
    NAME_PAYMENT_TYPE: str
    CODE_REJECT_REASON: str
    NAME_TYPE_SUITE: str | None = None
    NAME_CLIENT_TYPE: str
    NAME_GOODS_CATEGORY: str
    NAME_PORTFOLIO: str
    NAME_PRODUCT_TYPE: str
    CHANNEL_TYPE: str
    SELLERPLACE_AREA: int
    NAME_SELLER_INDUSTRY: str
    CNT_PAYMENT: float | None = None
    NAME_YIELD_GROUP: str
    PRODUCT_COMBINATION: str | None = None
    DAYS_FIRST_DRAWING: float | None = None
    DAYS_FIRST_DUE: float | None = None
    DAYS_LAST_DUE_1ST_VERSION: float | None = None
    DAYS_LAST_DUE: float | None = None
    DAYS_TERMINATION: float | None = None
    NFLAG_INSURED_ON_APPROVAL: float | None = None
