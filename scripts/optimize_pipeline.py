"""Optimized InferencePipeline wrappers — benchmark-only, API unchanged.

Patches two known Polars bottlenecks identified by pyinstrument profiling:

1. **InferencePipeline.predict()** — caches ``merged.columns`` as a ``set``
   to avoid repeated schema materialization on every feature-name check.
2. **BureauBalanceAggregator** — eliminates wasted lazy→collect→eager pattern,
   keeping the query plan lazy until the final ``.collect()``.

Usage::

    from scripts.optimize_pipeline import optimize
    pipeline = optimize(InferencePipeline.load(...))
    ids, probas = pipeline.predict(tables)       # optimized code path
"""

from __future__ import annotations

import copy
import functools
from typing import Any

import numpy as np
import polars as pl
from credit_risk_processing.data.aggregation.bureau_balance import (
    _BaseBureauBalanceAggregator,
    _bureau_agg_exprs,
    _compute_dpd,
    _curr_agg_exprs,
)
from credit_risk_processing.data.base import NoOpStep


def _optimized_predict(
    self_processing_pipelines: dict,
    self_model_pipeline: Any,
    self_feature_names: list[str],
    self_id_column: str,
    self_cross_transformer: Any,
    raw_tables: dict[str, pl.DataFrame],
) -> tuple[np.ndarray, np.ndarray]:
    """Patched version of InferencePipeline.predict() — schema caching."""
    processed: dict[str, pl.DataFrame] = {}

    for name, pipeline in self_processing_pipelines.items():
        if name not in raw_tables:
            continue
        out = pipeline.transform(raw_tables[name])
        processed[name] = _prefix_columns(out, name, self_id_column)

    if not processed:
        raise ValueError(
            "No tables were processed. Check that raw_tables keys match processing_pipelines keys."
        )

    table_names = list(processed)
    merged = processed[table_names[0]]
    for name in table_names[1:]:
        merged = merged.join(processed[name], on=self_id_column, how="left")

    if self_cross_transformer is not None and not isinstance(self_cross_transformer, NoOpStep):
        if hasattr(self_cross_transformer, "id_column"):
            self_cross_transformer.id_column = self_id_column
        cross_out = self_cross_transformer.transform(merged)
        cross_df = cross_out.get("cross")
        if cross_df is not None:
            cross_cols = [c for c in cross_df.columns if c != self_id_column]
            if cross_cols:
                merged = merged.join(
                    cross_df.select([self_id_column] + cross_cols),
                    on=self_id_column,
                    how="left",
                )

    ids = merged.select(self_id_column).to_series().to_numpy()

    # OPTIMIZATION: cache columns to a set once instead of per-feature checks
    existing_cols = set(merged.columns)

    for f in self_feature_names:
        if f not in existing_cols:
            merged = merged.with_columns(pl.lit(None).cast(pl.Float64).alias(f))
            existing_cols.add(f)

    X = merged.select(self_feature_names).to_numpy()
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    probas = self_model_pipeline.predict_proba(X)

    return ids, probas


def _prefix_columns(df: pl.DataFrame, prefix: str, id_column: str) -> pl.DataFrame:
    """Prefix all columns except id_column with table name."""
    rename_map = {}
    for col in df.columns:
        if col != id_column and not col.startswith(f"{prefix}_"):
            rename_map[col] = f"{prefix}_{col}"
    return df.rename(rename_map) if rename_map else df


def _patch_bureau_balance(step: _BaseBureauBalanceAggregator) -> None:
    """Replace transform() to avoid wasted lazy→collect→eager round-trip.

    The original pattern does::

        lf = X.lazy()
        lf = _compute_dpd(lf)
        lf = lf.collect()        # <-- premature materialization
        # ... eager operations ...

    Patched version keeps the plan lazy and only collects at the end::

        lf = X.lazy()
        lf = _compute_dpd(lf)
        lf = lf.group_by(...).agg(...)
        # ... lazy operations ...
        return result.collect()   # <-- single collect
    """
    bureaux_features = step.BUREAU_FEATURES

    @functools.wraps(step.transform)
    def patched_transform(X: pl.DataFrame, y=None) -> pl.DataFrame:
        lf = X.lazy()
        lf = _compute_dpd(lf)

        bb_agg = lf.group_by("SK_ID_BUREAU", "SK_ID_CURR").agg(*_bureau_agg_exprs(bureaux_features))

        recent = _patched_most_recent(lf)
        bb_agg = bb_agg.join(recent, on="SK_ID_BUREAU", how="left")

        return bb_agg.group_by("SK_ID_CURR").agg(*_curr_agg_exprs(bureaux_features)).collect()

    step.transform = patched_transform  # type: ignore[method-assign]


def _patched_most_recent(df: pl.LazyFrame) -> pl.LazyFrame:
    """LazyFrame version of _BaseBureauBalanceAggregator._most_recent."""
    return (
        df.filter(pl.col("MONTHS_BALANCE") == pl.col("MONTHS_BALANCE").max().over("SK_ID_BUREAU"))
        .group_by("SK_ID_BUREAU")
        .agg(pl.col("DPD").max().alias("bb_recent_dpd"))
    )


def _patch_pipeline_steps(
    processing_pipelines: dict[str, Any],
) -> dict[str, Any]:
    """Walk sklearn Pipelines and patch any BureauBalanceAggregator steps."""
    for _, pipe in processing_pipelines.items():
        if not hasattr(pipe, "steps"):
            continue
        for _, step in pipe.steps:
            if isinstance(step, _BaseBureauBalanceAggregator):
                _patch_bureau_balance(step)
    return processing_pipelines


def optimize(pipeline: Any) -> Any:
    """Return a patched copy of an InferencePipeline with optimizations applied.

    The original pipeline is not modified. A deep copy is used so the API
    retains the original behaviour.
    """
    patched = copy.deepcopy(pipeline)
    _patch_pipeline_steps(patched.processing_pipelines)
    # Replace predict with the optimized version, binding instance state
    p = patched
    patched.predict = lambda raw_tables, pp=p: _optimized_predict(
        pp.processing_pipelines,
        pp.model_pipeline,
        pp.feature_names,
        pp.id_column,
        pp.cross_transformer,
        raw_tables,
    )
    return patched
