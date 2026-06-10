"""Pydantic model for the application table (121 columns, inference only — no TARGET)."""

from pydantic import BaseModel, ConfigDict


class ApplicationRow(BaseModel):
    """Main application table row (121 columns, inference-only — no TARGET).

    Represents a single loan application with demographic, financial, and
    housing features.  This is the mandatory table in every prediction
    request — all other tables are optional supplementary data.
    """

    model_config = ConfigDict(extra="forbid")

    SK_ID_CURR: int
    NAME_CONTRACT_TYPE: str
    CODE_GENDER: str
    FLAG_OWN_CAR: str
    FLAG_OWN_REALTY: str
    CNT_CHILDREN: int
    AMT_INCOME_TOTAL: float
    AMT_CREDIT: float
    AMT_ANNUITY: float | None = None
    AMT_GOODS_PRICE: float
    NAME_TYPE_SUITE: str | None = None
    NAME_INCOME_TYPE: str
    NAME_EDUCATION_TYPE: str
    NAME_FAMILY_STATUS: str
    NAME_HOUSING_TYPE: str
    REGION_POPULATION_RELATIVE: float
    DAYS_BIRTH: int
    DAYS_EMPLOYED: int
    DAYS_REGISTRATION: float
    DAYS_ID_PUBLISH: int
    OWN_CAR_AGE: float | None = None
    FLAG_MOBIL: int
    FLAG_EMP_PHONE: int
    FLAG_WORK_PHONE: int
    FLAG_CONT_MOBILE: int
    FLAG_PHONE: int
    FLAG_EMAIL: int
    OCCUPATION_TYPE: str | None = None
    CNT_FAM_MEMBERS: float
    REGION_RATING_CLIENT: int
    REGION_RATING_CLIENT_W_CITY: int
    WEEKDAY_APPR_PROCESS_START: str
    HOUR_APPR_PROCESS_START: int
    REG_REGION_NOT_LIVE_REGION: int
    REG_REGION_NOT_WORK_REGION: int
    LIVE_REGION_NOT_WORK_REGION: int
    REG_CITY_NOT_LIVE_CITY: int
    REG_CITY_NOT_WORK_CITY: int
    LIVE_CITY_NOT_WORK_CITY: int
    ORGANIZATION_TYPE: str
    EXT_SOURCE_1: float | None = None
    EXT_SOURCE_2: float | None = None
    EXT_SOURCE_3: float | None = None
    APARTMENTS_AVG: float | None = None
    BASEMENTAREA_AVG: float | None = None
    YEARS_BEGINEXPLUATATION_AVG: float | None = None
    YEARS_BUILD_AVG: float | None = None
    COMMONAREA_AVG: float | None = None
    ELEVATORS_AVG: float | None = None
    ENTRANCES_AVG: float | None = None
    FLOORSMAX_AVG: float | None = None
    FLOORSMIN_AVG: float | None = None
    LANDAREA_AVG: float | None = None
    LIVINGAPARTMENTS_AVG: float | None = None
    LIVINGAREA_AVG: float | None = None
    NONLIVINGAPARTMENTS_AVG: float | None = None
    NONLIVINGAREA_AVG: float | None = None
    APARTMENTS_MODE: float | None = None
    BASEMENTAREA_MODE: float | None = None
    YEARS_BEGINEXPLUATATION_MODE: float | None = None
    YEARS_BUILD_MODE: float | None = None
    COMMONAREA_MODE: float | None = None
    ELEVATORS_MODE: float | None = None
    ENTRANCES_MODE: float | None = None
    FLOORSMAX_MODE: float | None = None
    FLOORSMIN_MODE: float | None = None
    LANDAREA_MODE: float | None = None
    LIVINGAPARTMENTS_MODE: float | None = None
    LIVINGAREA_MODE: float | None = None
    NONLIVINGAPARTMENTS_MODE: float | None = None
    NONLIVINGAREA_MODE: float | None = None
    APARTMENTS_MEDI: float | None = None
    BASEMENTAREA_MEDI: float | None = None
    YEARS_BEGINEXPLUATATION_MEDI: float | None = None
    YEARS_BUILD_MEDI: float | None = None
    COMMONAREA_MEDI: float | None = None
    ELEVATORS_MEDI: float | None = None
    ENTRANCES_MEDI: float | None = None
    FLOORSMAX_MEDI: float | None = None
    FLOORSMIN_MEDI: float | None = None
    LANDAREA_MEDI: float | None = None
    LIVINGAPARTMENTS_MEDI: float | None = None
    LIVINGAREA_MEDI: float | None = None
    NONLIVINGAPARTMENTS_MEDI: float | None = None
    NONLIVINGAREA_MEDI: float | None = None
    FONDKAPREMONT_MODE: str | None = None
    HOUSETYPE_MODE: str | None = None
    TOTALAREA_MODE: float | None = None
    WALLSMATERIAL_MODE: str | None = None
    EMERGENCYSTATE_MODE: str | None = None
    OBS_30_CNT_SOCIAL_CIRCLE: float | None = None
    DEF_30_CNT_SOCIAL_CIRCLE: float | None = None
    OBS_60_CNT_SOCIAL_CIRCLE: float | None = None
    DEF_60_CNT_SOCIAL_CIRCLE: float | None = None
    DAYS_LAST_PHONE_CHANGE: float
    FLAG_DOCUMENT_2: int
    FLAG_DOCUMENT_3: int
    FLAG_DOCUMENT_4: int
    FLAG_DOCUMENT_5: int
    FLAG_DOCUMENT_6: int
    FLAG_DOCUMENT_7: int
    FLAG_DOCUMENT_8: int
    FLAG_DOCUMENT_9: int
    FLAG_DOCUMENT_10: int
    FLAG_DOCUMENT_11: int
    FLAG_DOCUMENT_12: int
    FLAG_DOCUMENT_13: int
    FLAG_DOCUMENT_14: int
    FLAG_DOCUMENT_15: int
    FLAG_DOCUMENT_16: int
    FLAG_DOCUMENT_17: int
    FLAG_DOCUMENT_18: int
    FLAG_DOCUMENT_19: int
    FLAG_DOCUMENT_20: int
    FLAG_DOCUMENT_21: int
    AMT_REQ_CREDIT_BUREAU_HOUR: float | None = None
    AMT_REQ_CREDIT_BUREAU_DAY: float | None = None
    AMT_REQ_CREDIT_BUREAU_WEEK: float | None = None
    AMT_REQ_CREDIT_BUREAU_MON: float | None = None
    AMT_REQ_CREDIT_BUREAU_QRT: float | None = None
    AMT_REQ_CREDIT_BUREAU_YEAR: float | None = None
