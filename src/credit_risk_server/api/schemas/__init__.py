"""Pydantic schemas for the 7 input tables and prediction request/response."""

from credit_risk_server.api.schemas.application import ApplicationRow
from credit_risk_server.api.schemas.bureau import BureauRow
from credit_risk_server.api.schemas.bureau_balance import BureauBalanceRow
from credit_risk_server.api.schemas.credit_card_balance import CreditCardBalanceRow
from credit_risk_server.api.schemas.installments import InstallmentRow
from credit_risk_server.api.schemas.pos_cash_balance import PosCashBalanceRow
from credit_risk_server.api.schemas.prediction import (
    PredictFromSourceRequest,
    PredictRequest,
    PredictResponse,
)
from credit_risk_server.api.schemas.previous_application import PreviousApplicationRow

__all__ = [
    "ApplicationRow",
    "BureauRow",
    "BureauBalanceRow",
    "CreditCardBalanceRow",
    "InstallmentRow",
    "PosCashBalanceRow",
    "PreviousApplicationRow",
    "PredictFromSourceRequest",
    "PredictRequest",
    "PredictResponse",
]
