"""Tests for the data loading pipeline.

Covers: PolarsDataSource, assembler validation.
No FastAPI, no model — pure data layer.
"""

import polars as pl
import pytest

from credit_risk_server.core.exceptions import InvalidInputError
from credit_risk_server.data import assemble
from credit_risk_server.data.source import DataSource
from credit_risk_server.data.sources.polars import PolarsDataSource

MINIMAL_APP_ROW = {
    "SK_ID_CURR": 100001,
    "NAME_CONTRACT_TYPE": "Cash loans",
    "CODE_GENDER": "F",
    "FLAG_OWN_CAR": "N",
    "FLAG_OWN_REALTY": "Y",
    "CNT_CHILDREN": 0,
    "AMT_INCOME_TOTAL": 202500.0,
    "AMT_CREDIT": 500000.0,
    "AMT_GOODS_PRICE": 450000.0,
    "NAME_INCOME_TYPE": "Working",
    "NAME_EDUCATION_TYPE": "Secondary / secondary special",
    "NAME_FAMILY_STATUS": "Civil marriage",
    "NAME_HOUSING_TYPE": "House / apartment",
    "REGION_POPULATION_RELATIVE": 0.01885,
    "DAYS_BIRTH": -16765,
    "DAYS_EMPLOYED": -5643,
    "DAYS_REGISTRATION": -364.0,
    "DAYS_ID_PUBLISH": -4291,
    "FLAG_MOBIL": 1,
    "FLAG_EMP_PHONE": 1,
    "FLAG_WORK_PHONE": 0,
    "FLAG_CONT_MOBILE": 1,
    "FLAG_PHONE": 0,
    "FLAG_EMAIL": 0,
    "CNT_FAM_MEMBERS": 2.0,
    "REGION_RATING_CLIENT": 2,
    "REGION_RATING_CLIENT_W_CITY": 2,
    "WEEKDAY_APPR_PROCESS_START": "WEDNESDAY",
    "HOUR_APPR_PROCESS_START": 12,
    "REG_REGION_NOT_LIVE_REGION": 0,
    "REG_REGION_NOT_WORK_REGION": 0,
    "LIVE_REGION_NOT_WORK_REGION": 0,
    "REG_CITY_NOT_LIVE_CITY": 0,
    "REG_CITY_NOT_WORK_CITY": 0,
    "LIVE_CITY_NOT_WORK_CITY": 0,
    "ORGANIZATION_TYPE": "Business Entity Type 3",
    "DAYS_LAST_PHONE_CHANGE": -1134.0,
    "FLAG_DOCUMENT_2": 0,
    "FLAG_DOCUMENT_3": 1,
    "FLAG_DOCUMENT_4": 0,
    "FLAG_DOCUMENT_5": 0,
    "FLAG_DOCUMENT_6": 0,
    "FLAG_DOCUMENT_7": 0,
    "FLAG_DOCUMENT_8": 0,
    "FLAG_DOCUMENT_9": 0,
    "FLAG_DOCUMENT_10": 0,
    "FLAG_DOCUMENT_11": 0,
    "FLAG_DOCUMENT_12": 0,
    "FLAG_DOCUMENT_13": 0,
    "FLAG_DOCUMENT_14": 0,
    "FLAG_DOCUMENT_15": 0,
    "FLAG_DOCUMENT_16": 0,
    "FLAG_DOCUMENT_17": 0,
    "FLAG_DOCUMENT_18": 0,
    "FLAG_DOCUMENT_19": 0,
    "FLAG_DOCUMENT_20": 0,
    "FLAG_DOCUMENT_21": 0,
}

APP_ROW_2 = {**MINIMAL_APP_ROW, "SK_ID_CURR": 100002, "AMT_CREDIT": 300000.0}


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_polars_source_satisfies_protocol():
    source = PolarsDataSource(_FakeLoader({}))
    assert isinstance(source, DataSource)


# ---------------------------------------------------------------------------
# Assembler (raw DataFrames path)
# ---------------------------------------------------------------------------


def test_assemble_returns_dataframes():
    source = PolarsDataSource(
        _FakeLoader({"application": pl.DataFrame([MINIMAL_APP_ROW])}),
    )
    tables = assemble(source, sk_ids={100001})
    assert "application" in tables
    assert isinstance(tables["application"], pl.DataFrame)


def test_assemble_filters_by_sk_ids():
    source = PolarsDataSource(
        _FakeLoader(
            {"application": pl.DataFrame([MINIMAL_APP_ROW, APP_ROW_2])},
        ),
    )
    tables = assemble(source, sk_ids={100001})
    assert tables["application"].shape[0] == 1
    assert tables["application"]["SK_ID_CURR"][0] == 100001


def test_assemble_raises_on_empty_application():
    source = PolarsDataSource(
        _FakeLoader({"application": pl.DataFrame([MINIMAL_APP_ROW])}),
    )
    with pytest.raises(InvalidInputError, match="sk_ids"):
        assemble(source, sk_ids={999999})


# ---------------------------------------------------------------------------
# PredictFromSourceRequest validation
# ---------------------------------------------------------------------------


def test_predict_from_source_request_validates_sk_ids():
    from pydantic import ValidationError

    from credit_risk_server.api.schemas.prediction import PredictFromSourceRequest

    req = PredictFromSourceRequest(sk_ids=[100001, 100002])
    assert len(req.sk_ids) == 2

    with pytest.raises(ValidationError, match="sk_ids must not be empty"):
        PredictFromSourceRequest(sk_ids=[])


# ---------------------------------------------------------------------------
# PredictFromSourceRequest is forbidden from having extra fields
# ---------------------------------------------------------------------------


def test_predict_from_source_request_forbids_extra():
    from pydantic import ValidationError

    from credit_risk_server.api.schemas.prediction import PredictFromSourceRequest

    with pytest.raises(ValidationError):
        PredictFromSourceRequest(sk_ids=[100001], extra_field="bad")


# ---------------------------------------------------------------------------
# PolarsDataSource (with mock loader)
# ---------------------------------------------------------------------------


def test_polars_source_returns_table():
    df = pl.DataFrame([MINIMAL_APP_ROW])
    source = PolarsDataSource.from_loader(
        _FakeLoader({"application": df}),
    )
    result = source.get_table("application")
    assert result is not None
    assert result.shape[0] == 1


def test_polars_source_returns_none_for_missing_table():
    source = PolarsDataSource.from_loader(_FakeLoader({}))
    result = source.get_table("bureau")
    assert result is None


def test_polars_source_strips_target_column():
    row_with_target = {**MINIMAL_APP_ROW, "TARGET": 0}
    df = pl.DataFrame([row_with_target])
    source = PolarsDataSource.from_loader(
        _FakeLoader({"application": df}),
    )
    result = source.get_table("application")
    assert result is not None
    assert "TARGET" not in result.columns
    assert "SK_ID_CURR" in result.columns


def test_polars_source_strips_only_existing_columns():
    df = pl.DataFrame([MINIMAL_APP_ROW])
    source = PolarsDataSource.from_loader(
        _FakeLoader({"application": df}),
    )
    result = source.get_table("application")
    assert result is not None
    assert "TARGET" not in result.columns


def test_polars_source_filters_by_sk_ids():
    df = pl.DataFrame([MINIMAL_APP_ROW, APP_ROW_2])
    source = PolarsDataSource.from_loader(
        _FakeLoader({"application": df}),
    )
    result = source.get_table("application", sk_ids={100001})
    assert result is not None
    assert result.shape[0] == 1
    assert result["SK_ID_CURR"][0] == 100001


def test_polars_source_sk_ids_returns_none_when_empty():
    df = pl.DataFrame([MINIMAL_APP_ROW])
    source = PolarsDataSource.from_loader(
        _FakeLoader({"application": df}),
    )
    result = source.get_table("application", sk_ids={999999})
    assert result is None


# ---------------------------------------------------------------------------
# Helper: fake loader for PolarsDataSource tests
# ---------------------------------------------------------------------------


class _FakeLoader:
    """Minimal loader that returns pre-built DataFrames by table name."""

    def __init__(self, tables: dict[str, pl.DataFrame]) -> None:
        self._tables = tables

    def load(self, name: str) -> pl.DataFrame:
        if name not in self._tables:
            raise ValueError(f"Unknown table {name!r}")
        return self._tables[name]
