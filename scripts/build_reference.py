#!/usr/bin/env python3
"""Build the drift reference snapshot.

Samples ``SK_ID_CURR`` from ``application_test.csv``, assembles the seven raw
tables, runs the InferencePipeline, and persists:

- ``<out>/scores.parquet``      — reference prediction scores (one col ``score``)
- ``<out>/features.parquet``    — selected raw ``application`` features
- ``<out>/reference_meta.json`` — provenance (sample size, seed, build date, features)

The resulting snapshot is loaded at API startup by
:func:`credit_risk_server.monitoring.drift.load_reference`.

Usage::

    uv run python scripts/build_reference.py
    uv run python scripts/build_reference.py --sample 5000 --seed 42 --out data/reference
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
from credit_risk_data import PLLazyDataLoader
from credit_risk_models import InferencePipeline

from credit_risk_server.core.config import PROJECT_ROOT, api_settings
from credit_risk_server.data.assembler import assemble
from credit_risk_server.data.source import SOURCE_CSV_NAME_MAP
from credit_risk_server.data.sources.polars import PolarsDataSource
from credit_risk_server.monitoring.drift import DRIFT_FEATURES

logger = logging.getLogger("build_reference")

DEFAULT_OUT = PROJECT_ROOT / "data" / "reference"

# The reference baseline is the training distribution (what the model learned from),
# not the test holdout. Only the application CSV differs; the other six tables are
# shared and filtered by SK_ID_CURR.
REFERENCE_CSV_NAME_MAP = {**SOURCE_CSV_NAME_MAP, "application": "application_train.csv"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build the drift reference snapshot (scores + features).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--sample", type=int, default=307511, help="Number of SK_ID_CURR to sample")
    p.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    p.add_argument(
        "--model-path",
        type=Path,
        default=api_settings.model_path,
        help="Path to the InferencePipeline pickle",
    )
    p.add_argument(
        "--data-path",
        type=Path,
        default=api_settings.data_path,
        help="CSV data directory",
    )
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output reference directory")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    data_path = args.data_path
    if not data_path.is_absolute():
        data_path = PROJECT_ROOT / data_path

    # 1. Load application SK_ID_CURRs
    logger.info("loading application table", extra={"data_path": str(data_path)})
    loader = PLLazyDataLoader(data_path=data_path, csv_names=REFERENCE_CSV_NAME_MAP)
    source = PolarsDataSource.from_loader(loader)

    # Pull the unfiltered application frame to sample SK_ID_CURRs cheaply.
    app_full = loader.load("application")
    if isinstance(app_full, pl.LazyFrame):
        app_full = app_full.select("SK_ID_CURR").collect()
    sk_ids_all = app_full.get_column("SK_ID_CURR").unique().sort().to_list()

    n = min(args.sample, len(sk_ids_all))
    if n <= 0:
        logger.error("no SK_ID_CURR available to sample", extra={"available": len(sk_ids_all)})
        return 1
    logger.info("sampling SK_ID_CURRs", extra={"requested": args.sample, "chosen": n})
    rng = pl.Series(sk_ids_all).sample(n=n, seed=args.seed, shuffle=True)
    sk_ids = set(rng.to_list())

    # 2. Assemble raw tables for the sampled clients
    logger.info("assembling raw tables", extra={"sk_ids_count": len(sk_ids)})
    raw_tables = assemble(source, sk_ids=sk_ids)

    # 3. Load model and predict
    logger.info("loading model", extra={"model_path": str(args.model_path)})
    model = InferencePipeline.load(args.model_path)

    logger.info("running predictions")
    ids, probas = model.predict(raw_tables)
    scores_df = pl.DataFrame(
        {
            "SK_ID_CURR": ids,
            "score": probas,
        }
    )

    # 4. Extract features from the assembled application table
    app = raw_tables["application"]
    available = [c for c in DRIFT_FEATURES if c in app.columns]
    missing = [c for c in DRIFT_FEATURES if c not in app.columns]
    if missing:
        logger.warning("features not present in application table", extra={"missing": missing})
    features_df = app.select(["SK_ID_CURR", *available])

    # 5. Persist
    scores_path = out / "scores.parquet"
    features_path = out / "features.parquet"
    meta_path = out / "reference_meta.json"

    scores_df.write_parquet(scores_path)
    features_df.write_parquet(features_path)

    meta = {
        "build_date": datetime.now(tz=timezone.utc).isoformat(),
        "sample_size": len(sk_ids),
        "seed": args.seed,
        "model_path": str(args.model_path),
        "data_path": str(data_path),
        "score_count": scores_df.height,
        "features": list(available),
        "features_missing": missing,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    logger.info(
        "reference snapshot written",
        extra={
            "out": str(out),
            "scores": scores_df.height,
            "features": features_df.height,
            "feature_cols": len(available),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
