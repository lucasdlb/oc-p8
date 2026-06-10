"""Pydantic model for the bureau table (17 columns)."""

from pydantic import BaseModel, ConfigDict


class BureauRow(BaseModel):
    """Bureau table row (17 columns).

    One row per credit record from the Credit Bureau, linked to the
    current application via ``SK_ID_CURR``.
    """

    model_config = ConfigDict(extra="forbid")

    SK_ID_CURR: int
    SK_ID_BUREAU: int
    CREDIT_ACTIVE: str
    CREDIT_CURRENCY: str
    DAYS_CREDIT: int
    CREDIT_DAY_OVERDUE: int
    DAYS_CREDIT_ENDDATE: float | None = None
    DAYS_ENDDATE_FACT: float | None = None
    AMT_CREDIT_MAX_OVERDUE: float | None = None
    CNT_CREDIT_PROLONG: int
    AMT_CREDIT_SUM: float | None = None
    AMT_CREDIT_SUM_DEBT: float | None = None
    AMT_CREDIT_SUM_LIMIT: float | None = None
    AMT_CREDIT_SUM_OVERDUE: float
    CREDIT_TYPE: str
    DAYS_CREDIT_UPDATE: int
    AMT_ANNUITY: float | None = None
