#!/usr/bin/env python3
"""Benchmark ONNX Runtime inference vs native LightGBM.

Exports the LightGBM estimator to ONNX, then runs identical preprocessing
through both code paths. Measures per-batch latency, output agreement,
and memory impact.

Usage::

    uv run python scripts/bench_onnx.py                         # full benchmark
    uv run python scripts/bench_onnx.py --batch-sizes 1,50,500  # smoke run
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import polars as pl
from credit_risk_models import InferencePipeline
from onnxmltools.convert.common.data_types import FloatTensorType
from onnxmltools.convert.lightgbm import convert as convert_lgbm

from credit_risk_server.core.config import PROJECT_ROOT, api_settings
from credit_risk_server.monitoring.benchmark import (
    compute_stats,
    peak_rss_mb,
    throughput,
    time_callable,
)

# Suppress known benign warnings after all imports
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")
warnings.filterwarnings("ignore", message="Expected shape from model")
warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger("bench_onnx")

DEFAULT_OUT_DIR = PROJECT_ROOT / "docs" / "benchmark"
APPLICATION_CSV = "application_test.csv"
DEFAULT_BATCH_SIZES = [1, 5, 10, 25, 50, 100, 250, 500]


@dataclass(frozen=True)
class Config:
    name: str
    runs: int
    batch_sizes: list[int]
    warmup: int
    seed: int
    data_path: Path
    model_path: Path
    onnx_path: Path
    out_dir: Path


def parse_args() -> Config:
    p = argparse.ArgumentParser(
        description="Benchmark ONNX vs native LightGBM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--name", default="onnx")
    p.add_argument("--runs", type=int, default=20)
    p.add_argument("--batch-sizes", type=str, default=",".join(str(b) for b in DEFAULT_BATCH_SIZES))
    p.add_argument("--warmup", type=int, default=3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--data-path", type=Path, default=api_settings.data_path)
    p.add_argument("--model-path", type=Path, default=api_settings.model_path)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument(
        "--onnx-path",
        type=Path,
        default=Path("/tmp") / "lgbm_export.onnx",
        help="Path to cached ONNX model",
    )
    args = p.parse_args()

    return Config(
        name=args.name,
        runs=args.runs,
        batch_sizes=[int(b) for b in args.batch_sizes.split(",")],
        warmup=args.warmup,
        seed=args.seed,
        data_path=args.data_path,
        model_path=args.model_path,
        onnx_path=args.onnx_path,
        out_dir=args.out_dir,
    )


# ── ONNX helpers ──────────────────────────────────────────────────────────


def _strip_label_output(onnx_model: onnx.ModelProto) -> onnx.ModelProto:
    """Remove the label output from the ONNX graph — we only need probabilities.

    The label output has shape ``[1]`` (hardcoded by the converter), causing
    ONNX Runtime shape-mismatch warnings for batch sizes > 1.  Stripping it
    avoids needless warnings and drops an unused graph node.
    """
    graph = onnx_model.graph
    keep = [o for o in graph.output if o.name != "label"]
    if len(keep) < len(graph.output):
        del graph.output[:]
        graph.output.extend(keep)
    return onnx_model


def export_lightgbm(pipeline: InferencePipeline, onnx_path: Path) -> ort.InferenceSession:
    """Export LightGBM classifier from the pipeline to ONNX and return a session."""
    if onnx_path.exists():
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        return ort.InferenceSession(str(onnx_path), sess_options=opts)

    lgbm = pipeline.model_pipeline.get_final_estimator()
    n_features = len(pipeline.feature_names)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)

    initial_types = [("float_input", FloatTensorType([None, n_features]))]
    onnx_model = convert_lgbm(lgbm, initial_types=initial_types, zipmap=False)
    onnx_model = _strip_label_output(onnx_model)
    onnx.save_model(onnx_model, str(onnx_path))

    opts = ort.SessionOptions()
    opts.log_severity_level = 3
    return ort.InferenceSession(str(onnx_path), sess_options=opts)


def predict_native(
    pipeline: InferencePipeline, raw_tables: dict[str, pl.DataFrame]
) -> tuple[np.ndarray, np.ndarray]:
    """Full InferencePipeline path — native LightGBM."""
    return pipeline.predict(raw_tables)


def predict_onnx(
    pipeline: InferencePipeline,
    raw_tables: dict[str, pl.DataFrame],
    session: ort.InferenceSession,
) -> tuple[np.ndarray, np.ndarray]:
    """Same preprocessing as InferencePipeline.predict(), but uses ONNX Runtime."""
    processed: dict[str, pl.DataFrame] = {}
    for name, pipe in pipeline.processing_pipelines.items():
        if name not in raw_tables:
            continue
        out = pipe.transform(raw_tables[name])
        processed[name] = pipeline._prefix_columns(out, name)

    if not processed:
        raise ValueError("No tables were processed")

    table_names = list(processed)
    merged = processed[table_names[0]]
    for name in table_names[1:]:
        merged = merged.join(processed[name], on=pipeline.id_column, how="left")

    if pipeline.cross_transformer is not None:
        from credit_risk_processing.data.base import NoOpStep

        if not isinstance(pipeline.cross_transformer, NoOpStep):
            cross_out = pipeline.cross_transformer.transform(merged)
            cross_df = cross_out.get("cross")
            if cross_df is not None:
                cross_cols = [c for c in cross_df.columns if c != pipeline.id_column]
                if cross_cols:
                    merged = merged.join(
                        cross_df.select([pipeline.id_column] + cross_cols),
                        on=pipeline.id_column,
                        how="left",
                    )

    ids = merged.select(pipeline.id_column).to_series().to_numpy()

    for f in pipeline.feature_names:
        if f not in merged.columns:
            merged = merged.with_columns(pl.lit(None).cast(pl.Float64).alias(f))

    X = merged.select(pipeline.feature_names).to_numpy()
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    input_name = session.get_inputs()[0].name
    probas = session.run(None, {input_name: X.astype(np.float32)})[0][:, 1]

    return ids, probas


# ── Benchmark orchestration ──────────────────────────────────────────────


def load_row_dicts(data_path: Path) -> list[dict]:
    csv_file = data_path / APPLICATION_CSV
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV not found: {csv_file}")
    df = pl.read_csv(csv_file)
    return df.to_dicts()


def make_tables_from_rows(
    row_dicts: list[dict],
    pipeline: InferencePipeline,
) -> dict[str, pl.DataFrame]:
    """Build the 7-table dict from a single application row sample.

    Only the application table is populated (this is the /predict/rows path).
    Other tables are silently skipped by the pipeline.
    """
    app_df = pl.DataFrame(row_dicts)
    return {"application": app_df}


def collect_environment(cfg: Config) -> dict:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "model_file": str(cfg.model_path),
        "data_path": str(cfg.data_path),
        "onnx_path": str(cfg.onnx_path),
    }


def _make_native_fn(pipeline, tables):
    return lambda: predict_native(pipeline, tables)


def _make_onnx_fn(pipeline, tables, session):
    return lambda: predict_onnx(pipeline, tables, session)


def run_benchmark(cfg: Config, pipeline: InferencePipeline, session: ort.InferenceSession) -> dict:
    row_dicts = load_row_dicts(cfg.data_path)
    sys.stderr.write(f"Application row pool: {len(row_dicts)} rows\n\n")
    sys.stderr.flush()

    # ── Agreement test (single batch) ──
    sys.stderr.write("Phase 1: Output agreement check...\n")
    sys.stderr.flush()
    sample = row_dicts[: min(50, len(row_dicts))]
    tables = make_tables_from_rows(sample, pipeline)

    ids_native, probas_native = predict_native(pipeline, tables)
    ids_onnx, probas_onnx = predict_onnx(pipeline, tables, session)

    assert np.array_equal(ids_native, ids_onnx), "ID mismatch between native and ONNX"
    proba_diff = np.max(np.abs(probas_native - probas_onnx))
    sys.stderr.write(f"  max probability diff: {proba_diff:.2e}\n\n")
    sys.stderr.flush()

    # ── Batch sweep (full pipeline) ──
    sys.stderr.write(
        f"Phase 2: Batch sweep — full pipeline (warmup={cfg.warmup}, runs={cfg.runs})...\n\n"
    )
    sys.stderr.flush()

    native_results: dict[str, dict] = {}
    onnx_results: dict[str, dict] = {}

    for bs in cfg.batch_sizes:
        sample = row_dicts[: min(bs, len(row_dicts))]
        tables = make_tables_from_rows(sample, pipeline)

        # Native
        native_fn = _make_native_fn(pipeline, tables)
        for _ in range(cfg.warmup):
            native_fn()
        native_lats: list[float] = []
        for _ in range(cfg.runs):
            _, ms = time_callable(native_fn)
            native_lats.append(ms)
        native_stats = compute_stats(native_lats)
        native_stats["throughput_preds_per_sec"] = throughput(bs, native_stats["mean_ms"] / 1000.0)
        native_stats["per_prediction_ms"] = round(native_stats["mean_ms"] / bs, 2)
        native_results[str(bs)] = native_stats

        # ONNX
        onnx_fn = _make_onnx_fn(pipeline, tables, session)
        for _ in range(cfg.warmup):
            onnx_fn()
        onnx_lats: list[float] = []
        for _ in range(cfg.runs):
            _, ms = time_callable(onnx_fn)
            onnx_lats.append(ms)
        onnx_stats = compute_stats(onnx_lats)
        onnx_stats["throughput_preds_per_sec"] = throughput(bs, onnx_stats["mean_ms"] / 1000.0)
        onnx_stats["per_prediction_ms"] = round(onnx_stats["mean_ms"] / bs, 2)
        onnx_results[str(bs)] = onnx_stats

        sys.stderr.write(
            f"  batch={bs:>4}: native={native_stats['mean_ms']:>7.1f}ms "
            f"onnx={onnx_stats['mean_ms']:>7.1f}ms "
            f"diff={native_stats['mean_ms'] - onnx_stats['mean_ms']:>+7.1f}ms "
            f"(tput: {native_stats['throughput_preds_per_sec']:>7.1f} vs "
            f"{onnx_stats['throughput_preds_per_sec']:>7.1f} p/s)\n"
        )
        sys.stderr.flush()

    # ── Model-only benchmark ──
    # Isolate just the final inference step (after identical preprocessing)
    # to measure ONNX vs native LightGBM directly, without preprocessing noise.
    sys.stderr.write(f"\nPhase 3: Model-only inference timing (runs={cfg.runs})...\n")
    sys.stderr.flush()

    sample = row_dicts[: min(50, len(row_dicts))]
    tables = make_tables_from_rows(sample, pipeline)

    # Run preprocessing once (shared cost)
    lgbm_model = pipeline.model_pipeline
    n_features = len(pipeline.feature_names)
    input_name = session.get_inputs()[0].name

    # Get the numpy features (same preprocessing shared between both paths)
    processed: dict[str, pl.DataFrame] = {}
    for name, pipe in pipeline.processing_pipelines.items():
        if name not in tables:
            continue
        out = pipe.transform(tables[name])
        processed[name] = pipeline._prefix_columns(out, name)
    merged = processed[list(processed)[0]]
    for name in list(processed)[1:]:
        merged = merged.join(processed[name], on=pipeline.id_column, how="left")
    if pipeline.cross_transformer is not None:
        from credit_risk_processing.data.base import NoOpStep

        if not isinstance(pipeline.cross_transformer, NoOpStep):
            cross_out = pipeline.cross_transformer.transform(merged)
            cross_df = cross_out.get("cross")
            if cross_df is not None:
                cross_cols = [c for c in cross_df.columns if c != pipeline.id_column]
                if cross_cols:
                    merged = merged.join(
                        cross_df.select([pipeline.id_column] + cross_cols),
                        on=pipeline.id_column,
                        how="left",
                    )
    missing_features = [f for f in pipeline.feature_names if f not in merged.columns]
    merged = merged.with_columns([pl.lit(None).cast(pl.Float64).alias(f) for f in missing_features])
    X = merged.select(pipeline.feature_names).to_numpy()
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

    # Benchmark native model inference only
    native_model_lats: list[float] = []
    for _ in range(cfg.runs):
        _, ms = time_callable(lambda: lgbm_model.predict_proba(X))
        native_model_lats.append(ms)
    native_model_stats = compute_stats(native_model_lats)

    # Benchmark ONNX model inference only
    X_f32 = X.astype(np.float32)
    onnx_model_lats: list[float] = []
    for _ in range(cfg.runs):
        _, ms = time_callable(lambda: session.run(None, {input_name: X_f32}))
        onnx_model_lats.append(ms)
    onnx_model_stats = compute_stats(onnx_model_lats)

    n_mean = native_model_stats["mean_ms"]
    o_mean = onnx_model_stats["mean_ms"]
    model_improvement = (n_mean - o_mean) / n_mean * 100 if n_mean > 0 else 0.0

    sys.stderr.write(
        f"  Native model: mean={native_model_stats['mean_ms']:.3f}ms  "
        f"p50={native_model_stats['p50_ms']:.3f}ms  "
        f"p95={native_model_stats['p95_ms']:.3f}ms\n"
    )
    sys.stderr.write(
        f"  ONNX   model: mean={onnx_model_stats['mean_ms']:.3f}ms  "
        f"p50={onnx_model_stats['p50_ms']:.3f}ms  "
        f"p95={onnx_model_stats['p95_ms']:.3f}ms\n"
    )
    sys.stderr.write(f"  Model-only improvement: {model_improvement:+.2f}%\n")
    sys.stderr.flush()

    # ── Summary ──
    native_mean_overall = np.mean([v["mean_ms"] for v in native_results.values()])
    onnx_mean_overall = np.mean([v["mean_ms"] for v in onnx_results.values()])
    pipeline_improvement = (
        (native_mean_overall - onnx_mean_overall) / native_mean_overall * 100
        if native_mean_overall > 0
        else 0.0
    )

    sys.stderr.write("\nSummary:\n")
    sys.stderr.write(
        f"  Full pipeline — Native mean: {native_mean_overall:.1f}ms  "
        f"ONNX mean: {onnx_mean_overall:.1f}ms  ({pipeline_improvement:+.2f}%)\n"
    )
    sys.stderr.write(
        f"  Model only   — Native mean: {native_model_stats['mean_ms']:.3f}ms  "
        f"ONNX mean: {onnx_model_stats['mean_ms']:.3f}ms  ({model_improvement:+.2f}%)\n"
    )
    sys.stderr.flush()

    return {
        "name": cfg.name,
        "script": "bench_onnx",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "environment": collect_environment(cfg),
        "agreement": {
            "probas_max_diff": round(float(proba_diff), 12),
            "ids_match": True,
        },
        "native": native_results,
        "onnx": onnx_results,
        "model_inference": {
            "native": native_model_stats,
            "onnx": onnx_model_stats,
            "improvement_pct": round(float(model_improvement), 2),
            "n_features": n_features,
        },
        "summary": {
            "pipeline": {
                "native_mean_ms": round(float(native_mean_overall), 2),
                "onnx_mean_ms": round(float(onnx_mean_overall), 2),
                "improvement_pct": round(float(pipeline_improvement), 2),
            },
        },
        "peak_rss_mb": peak_rss_mb(),
    }


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    cfg = parse_args()
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    sys.stderr.write(f"Benchmark ONNX vs Native — name={cfg.name} | runs={cfg.runs}\n\n")
    sys.stderr.flush()

    sys.stderr.write("Loading InferencePipeline...\n")
    sys.stderr.flush()
    pipeline = InferencePipeline.load(cfg.model_path)

    sys.stderr.write("Exporting LightGBM to ONNX (or loading cached)...\n")
    sys.stderr.flush()
    session = export_lightgbm(pipeline, cfg.onnx_path)

    sys.stderr.write(f"ONNX model: {cfg.onnx_path}\n")
    sys.stderr.write(
        f"ONNX session: {session.get_inputs()[0].name} shape={session.get_inputs()[0].shape}\n\n"
    )
    sys.stderr.flush()

    report = run_benchmark(cfg, pipeline, session)

    out_json = cfg.out_dir / f"onnx_{cfg.name}.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    sys.stderr.write(f"\nResults saved: {out_json}\n")
    sys.stderr.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
