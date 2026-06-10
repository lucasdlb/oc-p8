"""Pydantic models for prediction requests and response."""

from pydantic import BaseModel, ConfigDict, field_validator

from credit_risk_server.api.schemas.application import ApplicationRow
from credit_risk_server.api.schemas.bureau import BureauRow
from credit_risk_server.api.schemas.bureau_balance import BureauBalanceRow
from credit_risk_server.api.schemas.credit_card_balance import CreditCardBalanceRow
from credit_risk_server.api.schemas.installments import InstallmentRow
from credit_risk_server.api.schemas.pos_cash_balance import PosCashBalanceRow
from credit_risk_server.api.schemas.previous_application import PreviousApplicationRow


class PredictRequest(BaseModel):
    """Row-oriented request — client sends all table data."""

    model_config = ConfigDict(extra="forbid")

    application: list[ApplicationRow]
    bureau: list[BureauRow] | None = None
    bureau_balance: list[BureauBalanceRow] | None = None
    previous_application: list[PreviousApplicationRow] | None = None
    pos_cash_balance: list[PosCashBalanceRow] | None = None
    installments: list[InstallmentRow] | None = None
    credit_card_balance: list[CreditCardBalanceRow] | None = None


class PredictFromSourceRequest(BaseModel):
    """Source-based request — client sends sk_ids, API loads data from configured source."""

    model_config = ConfigDict(extra="forbid")

    sk_ids: list[int]

    @field_validator("sk_ids")
    @classmethod
    def sk_ids_must_not_be_empty(cls, v: list[int]) -> list[int]:
        """Reject empty ``sk_ids`` — at least one client must be requested."""
        if not v:
            raise ValueError("sk_ids must not be empty")
        return v


class PredictResponse(BaseModel):
    """Single prediction result — client identifier and default probability."""

    model_config = ConfigDict(extra="forbid")

    sk_id_curr: int
    probability: float
