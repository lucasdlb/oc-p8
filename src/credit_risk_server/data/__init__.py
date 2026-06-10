"""Data loading layer — DataSource protocol + concrete implementations.

Public API:
    from credit_risk_server.data import assemble, DataSource, make_source
    from credit_risk_server.data.sources.polars import PolarsDataSource
    from credit_risk_server.data.sources.sql import SqlDataSource
"""

from credit_risk_server.data.assembler import assemble
from credit_risk_server.data.factory import make_source
from credit_risk_server.data.source import SOURCE_CSV_NAME_MAP, TABLE_NAMES, DataSource

__all__ = [
    "assemble",
    "DataSource",
    "make_source",
    "SOURCE_CSV_NAME_MAP",
    "TABLE_NAMES",
]
