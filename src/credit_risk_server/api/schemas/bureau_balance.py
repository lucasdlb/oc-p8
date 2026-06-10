"""Pydantic model for the bureau_balance table.

Raw CSV has only SK_ID_BUREAU, MONTHS_BALANCE, STATUS.
SK_ID_CURR is required by the InferencePipeline's two-level aggregation
(SK_ID_BUREAU → SK_ID_CURR). The client must provide it pre-joined.
"""

from pydantic import BaseModel, ConfigDict


class BureauBalanceRow(BaseModel):
    """Bureau balance row (4 columns).

    Monthly balance history for a bureau credit record.  The raw CSV only
    contains ``SK_ID_BUREAU``, ``MONTHS_BALANCE``, and ``STATUS``; however
    ``SK_ID_CURR`` is required here because the
    :class:`~credit_risk_models.InferencePipeline` performs a two-level
    aggregation (``SK_ID_BUREAU`` → ``SK_ID_CURR``).  The client must
    provide it pre-joined.
    """

    model_config = ConfigDict(extra="forbid")

    SK_ID_CURR: int
    SK_ID_BUREAU: int
    MONTHS_BALANCE: int
    STATUS: str
