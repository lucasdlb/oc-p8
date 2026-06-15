"""Validation tests for Pydantic schema models — all 7 tables, request, response."""

import pytest
from conftest import MINIMAL_APP_ROW
from pydantic import ValidationError

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

# ---------------------------------------------------------------------------
# ApplicationRow
# ---------------------------------------------------------------------------


class TestApplicationRow:
    def test_valid_minimal(self):
        row = ApplicationRow(**MINIMAL_APP_ROW)
        assert row.SK_ID_CURR == 100001

    def test_missing_required_field(self):
        data = {**MINIMAL_APP_ROW}
        del data["SK_ID_CURR"]
        with pytest.raises(ValidationError, match="SK_ID_CURR"):
            ApplicationRow(**data)

    def test_extra_field_rejected(self):
        data = {**MINIMAL_APP_ROW, "UNKNOWN_COL": 99}
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            ApplicationRow(**data)

    def test_wrong_type_int_field(self):
        data = {**MINIMAL_APP_ROW, "SK_ID_CURR": "not_an_int"}
        with pytest.raises(ValidationError):
            ApplicationRow(**data)

    def test_wrong_type_float_field(self):
        data = {**MINIMAL_APP_ROW, "AMT_CREDIT": "not_a_float"}
        with pytest.raises(ValidationError):
            ApplicationRow(**data)

    def test_optional_none_allowed(self):
        data = {**MINIMAL_APP_ROW, "AMT_ANNUITY": None}
        row = ApplicationRow(**data)
        assert row.AMT_ANNUITY is None

    def test_optional_string_none_allowed(self):
        data = {**MINIMAL_APP_ROW, "OCCUPATION_TYPE": None}
        row = ApplicationRow(**data)
        assert row.OCCUPATION_TYPE is None


# ---------------------------------------------------------------------------
# BureauRow
# ---------------------------------------------------------------------------


class TestBureauRow:
    def test_valid_minimal(self):
        row = BureauRow(
            SK_ID_CURR=100001,
            SK_ID_BUREAU=5000001,
            CREDIT_ACTIVE="Closed",
            CREDIT_CURRENCY="currency 1",
            DAYS_CREDIT=-100,
            CREDIT_DAY_OVERDUE=0,
            CNT_CREDIT_PROLONG=0,
            AMT_CREDIT_SUM_OVERDUE=0.0,
            CREDIT_TYPE="Consumer credit",
            DAYS_CREDIT_UPDATE=-50,
        )
        assert row.SK_ID_BUREAU == 5000001

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            BureauRow(SK_ID_CURR=100001)

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError, match="Extra inputs"):
            BureauRow(
                SK_ID_CURR=100001,
                SK_ID_BUREAU=1,
                CREDIT_ACTIVE="Closed",
                CREDIT_CURRENCY="currency 1",
                DAYS_CREDIT=-1,
                CREDIT_DAY_OVERDUE=0,
                CNT_CREDIT_PROLONG=0,
                AMT_CREDIT_SUM_OVERDUE=0.0,
                CREDIT_TYPE="Consumer credit",
                DAYS_CREDIT_UPDATE=-1,
                extra="bad",
            )


# ---------------------------------------------------------------------------
# BureauBalanceRow
# ---------------------------------------------------------------------------


class TestBureauBalanceRow:
    def test_valid(self):
        row = BureauBalanceRow(
            SK_ID_CURR=100001,
            SK_ID_BUREAU=5000001,
            MONTHS_BALANCE=-1,
            STATUS="C",
        )
        assert row.STATUS == "C"

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            BureauBalanceRow(SK_ID_CURR=100001)


# ---------------------------------------------------------------------------
# PreviousApplicationRow
# ---------------------------------------------------------------------------


class TestPreviousApplicationRow:
    def test_valid_minimal(self):
        row = PreviousApplicationRow(
            SK_ID_PREV=2000001,
            SK_ID_CURR=100001,
            NAME_CONTRACT_TYPE="Cash loans",
            AMT_APPLICATION=100000.0,
            WEEKDAY_APPR_PROCESS_START="MONDAY",
            HOUR_APPR_PROCESS_START=10,
            FLAG_LAST_APPL_PER_CONTRACT="Y",
            NFLAG_LAST_APPL_IN_DAY=1,
            NAME_CASH_LOAN_PURPOSE="XAP",
            NAME_CONTRACT_STATUS="Approved",
            DAYS_DECISION=-100,
            NAME_PAYMENT_TYPE="Cash through the bank",
            CODE_REJECT_REASON="XAP",
            NAME_CLIENT_TYPE="Repeater",
            NAME_GOODS_CATEGORY="XNA",
            NAME_PORTFOLIO="POS",
            NAME_PRODUCT_TYPE="x-sell",
            CHANNEL_TYPE="Country-wide",
            SELLERPLACE_AREA=1,
            NAME_SELLER_INDUSTRY="XNA",
            NAME_YIELD_GROUP="low_normal",
        )
        assert row.SK_ID_PREV == 2000001

    def test_optional_fields_accept_none(self):
        row = PreviousApplicationRow(
            SK_ID_PREV=2000001,
            SK_ID_CURR=100001,
            NAME_CONTRACT_TYPE="Cash loans",
            AMT_APPLICATION=100000.0,
            WEEKDAY_APPR_PROCESS_START="MONDAY",
            HOUR_APPR_PROCESS_START=10,
            FLAG_LAST_APPL_PER_CONTRACT="Y",
            NFLAG_LAST_APPL_IN_DAY=1,
            NAME_CASH_LOAN_PURPOSE="XAP",
            NAME_CONTRACT_STATUS="Approved",
            DAYS_DECISION=-100,
            NAME_PAYMENT_TYPE="Cash through the bank",
            CODE_REJECT_REASON="XAP",
            NAME_CLIENT_TYPE="Repeater",
            NAME_GOODS_CATEGORY="XNA",
            NAME_PORTFOLIO="POS",
            NAME_PRODUCT_TYPE="x-sell",
            CHANNEL_TYPE="Country-wide",
            SELLERPLACE_AREA=1,
            NAME_SELLER_INDUSTRY="XNA",
            NAME_YIELD_GROUP="low_normal",
            AMT_ANNUITY=None,
            AMT_CREDIT=None,
        )
        assert row.AMT_ANNUITY is None


# ---------------------------------------------------------------------------
# PosCashBalanceRow
# ---------------------------------------------------------------------------


class TestPosCashBalanceRow:
    def test_valid(self):
        row = PosCashBalanceRow(
            SK_ID_PREV=2000001,
            SK_ID_CURR=100001,
            MONTHS_BALANCE=-1,
            NAME_CONTRACT_STATUS="Active",
            SK_DPD=0,
            SK_DPD_DEF=0,
        )
        assert row.SK_ID_PREV == 2000001

    def test_missing_required(self):
        with pytest.raises(ValidationError):
            PosCashBalanceRow(SK_ID_PREV=1)


# ---------------------------------------------------------------------------
# InstallmentRow
# ---------------------------------------------------------------------------


class TestInstallmentRow:
    def test_valid(self):
        row = InstallmentRow(
            SK_ID_PREV=2000001,
            SK_ID_CURR=100001,
            NUM_INSTALMENT_VERSION=1.0,
            NUM_INSTALMENT_NUMBER=1,
            DAYS_INSTALMENT=-30.0,
            AMT_INSTALMENT=5000.0,
        )
        assert row.SK_ID_PREV == 2000001

    def test_optional_none(self):
        row = InstallmentRow(
            SK_ID_PREV=2000001,
            SK_ID_CURR=100001,
            NUM_INSTALMENT_VERSION=1.0,
            NUM_INSTALMENT_NUMBER=1,
            DAYS_INSTALMENT=-30.0,
            AMT_INSTALMENT=5000.0,
            DAYS_ENTRY_PAYMENT=None,
            AMT_PAYMENT=None,
        )
        assert row.AMT_PAYMENT is None


# ---------------------------------------------------------------------------
# CreditCardBalanceRow
# ---------------------------------------------------------------------------


class TestCreditCardBalanceRow:
    def test_valid_minimal(self):
        row = CreditCardBalanceRow(
            SK_ID_PREV=2000001,
            SK_ID_CURR=100001,
            MONTHS_BALANCE=-1,
            AMT_BALANCE=1000.0,
            AMT_CREDIT_LIMIT_ACTUAL=50000,
            AMT_DRAWINGS_CURRENT=500.0,
            AMT_PAYMENT_TOTAL_CURRENT=200.0,
            AMT_RECEIVABLE_PRINCIPAL=800.0,
            AMT_RECIVABLE=800.0,
            AMT_TOTAL_RECEIVABLE=800.0,
            CNT_DRAWINGS_CURRENT=2,
            NAME_CONTRACT_STATUS="Active",
            SK_DPD=0,
            SK_DPD_DEF=0,
        )
        assert row.SK_ID_PREV == 2000001


# ---------------------------------------------------------------------------
# PredictRequest
# ---------------------------------------------------------------------------


class TestPredictRequest:
    def test_valid_with_application_only(self):
        app_rows = [ApplicationRow(**MINIMAL_APP_ROW)]
        req = PredictRequest(application=app_rows)
        assert len(req.application) == 1
        assert req.bureau is None

    def test_valid_with_optional_tables(self):
        app_rows = [ApplicationRow(**MINIMAL_APP_ROW)]
        bureau_rows = [
            BureauRow(
                SK_ID_CURR=100001,
                SK_ID_BUREAU=5000001,
                CREDIT_ACTIVE="Closed",
                CREDIT_CURRENCY="currency 1",
                DAYS_CREDIT=-100,
                CREDIT_DAY_OVERDUE=0,
                CNT_CREDIT_PROLONG=0,
                AMT_CREDIT_SUM_OVERDUE=0.0,
                CREDIT_TYPE="Consumer credit",
                DAYS_CREDIT_UPDATE=-50,
            ),
        ]
        req = PredictRequest(application=app_rows, bureau=bureau_rows)
        assert len(req.bureau) == 1

    def test_forbids_extra_fields(self):
        app_rows = [ApplicationRow(**MINIMAL_APP_ROW)]
        with pytest.raises(ValidationError, match="Extra inputs"):
            PredictRequest(application=app_rows, unexpected="bad")

    def test_empty_application_list_is_valid_schema(self):
        req = PredictRequest(application=[])
        assert req.application == []


# ---------------------------------------------------------------------------
# PredictFromSourceRequest
# ---------------------------------------------------------------------------


class TestPredictFromSourceRequest:
    def test_valid(self):
        req = PredictFromSourceRequest(sk_ids=[100001, 100002])
        assert len(req.sk_ids) == 2

    def test_empty_sk_ids_rejected(self):
        with pytest.raises(ValidationError, match="sk_ids must not be empty"):
            PredictFromSourceRequest(sk_ids=[])

    def test_sk_ids_must_be_integers(self):
        with pytest.raises(ValidationError):
            PredictFromSourceRequest(sk_ids=["abc"])

    def test_forbids_extra_fields(self):
        with pytest.raises(ValidationError, match="Extra inputs"):
            PredictFromSourceRequest(sk_ids=[100001], extra="bad")


# ---------------------------------------------------------------------------
# PredictResponse
# ---------------------------------------------------------------------------


class TestPredictResponse:
    def test_valid(self):
        resp = PredictResponse(sk_id_curr=100001, probability=0.42)
        assert resp.sk_id_curr == 100001
        assert resp.probability == pytest.approx(0.42)

    def test_forbids_extra_fields(self):
        with pytest.raises(ValidationError, match="Extra inputs"):
            PredictResponse(sk_id_curr=100001, probability=0.42, extra="bad")

    def test_wrong_type_sk_id(self):
        with pytest.raises(ValidationError):
            PredictResponse(sk_id_curr="not_int", probability=0.5)

    def test_wrong_type_probability(self):
        with pytest.raises(ValidationError):
            PredictResponse(sk_id_curr=100001, probability="not_float")
