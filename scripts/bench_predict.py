#!/usr/bin/env python3
"""Benchmark — /predict code path (DataSource → assemble → InferencePipeline).

Measures startup phases, cold start, batch-size sweep, concurrency behavior,
memory growth, output determinism, and profiling for the DataSource path
(`/predict`). All measurements are in-process (no HTTP/uvicorn overhead).

Usage::

    # Full baseline
    uv run python scripts/bench_predict.py --name baseline

    # Smoke test (fast, validates behavior)
    uv run python scripts/bench_predict.py --name smoke \\
        --batch-sizes 1,50 --runs 3 --no-concurrency --no-memory --no-determinism
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import random
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import polars as pl
from credit_risk_data import PLLazyDataLoader
from credit_risk_models import InferencePipeline

from credit_risk_server.core.config import PROJECT_ROOT, api_settings
from credit_risk_server.data.assembler import assemble
from credit_risk_server.data.source import SOURCE_CSV_NAME_MAP
from credit_risk_server.data.sources.polars import PolarsDataSource
from credit_risk_server.monitoring.benchmark import (
    peak_rss_mb,
    profile_predict,
    run_batch_sweep,
    run_concurrency,
    run_determinism,
    run_memory_growth,
    time_callable,
)

logger = logging.getLogger("bench_predict")

DEFAULT_OUT_DIR = PROJECT_ROOT / "docs" / "benchmark"
APPLICATION_CSV = "application_test.csv"
DEFAULT_BATCH_SIZES = [1, 5, 10, 25, 50, 100, 250, 500]
DEFAULT_WORKERS = [1, 2, 4, 8, 16]


@dataclass(frozen=True)
class Config:
    name: str
    runs: int
    batch_sizes: list[int]
    workers: list[int]
    concurrency_tasks: int
    memory_predictions: int
    memory_sample_every: int
    determinism_runs: int
    profile_iterations: int
    warmup: int
    seed: int
    data_path: Path
    model_path: Path
    out_dir: Path
    skip_concurrency: bool
    skip_memory: bool
    skip_determinism: bool
    skip_profile: bool


def parse_args() -> Config:
    p = argparse.ArgumentParser(
        description="Benchmark /predict code path (DataSource → assemble → InferencePipeline)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--name", default="baseline", help="Run name (used in output filenames)")
    p.add_argument("--runs", type=int, default=20, help="Timed runs per batch size")
    p.add_argument(
        "--batch-sizes",
        type=str,
        default=",".join(str(b) for b in DEFAULT_BATCH_SIZES),
        help="Comma-separated batch sizes to sweep",
    )
    p.add_argument(
        "--workers",
        type=str,
        default=",".join(str(w) for w in DEFAULT_WORKERS),
        help="Comma-separated concurrency worker counts",
    )
    p.add_argument("--concurrency-tasks", type=int, default=50, help="Tasks per concurrency config")
    p.add_argument(
        "--memory-predictions", type=int, default=1000, help="Sequential preds for memory growth"
    )
    p.add_argument("--memory-sample-every", type=int, default=100, help="RSS sample interval")
    p.add_argument("--determinism-runs", type=int, default=50, help="Runs for determinism check")
    p.add_argument(
        "--profile-iterations", type=int, default=20, help="Iterations inside pyinstrument"
    )
    p.add_argument("--warmup", type=int, default=3, help="Warmup runs discarded per batch size")
    p.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    p.add_argument(
        "--data-path", type=Path, default=api_settings.data_path, help="CSV data directory"
    )
    p.add_argument(
        "--model-path", type=Path, default=api_settings.model_path, help="Model pickle path"
    )
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory")
    p.add_argument("--no-concurrency", action="store_true", help="Skip concurrency sweep")
    p.add_argument("--no-memory", action="store_true", help="Skip memory growth test")
    p.add_argument("--no-determinism", action="store_true", help="Skip determinism check")
    p.add_argument("--no-profile", action="store_true", help="Skip pyinstrument profiling")
    args = p.parse_args()

    return Config(
        name=args.name,
        runs=args.runs,
        batch_sizes=[int(b) for b in args.batch_sizes.split(",")],
        workers=[int(w) for w in args.workers.split(",")],
        concurrency_tasks=args.concurrency_tasks,
        memory_predictions=args.memory_predictions,
        memory_sample_every=args.memory_sample_every,
        determinism_runs=args.determinism_runs,
        profile_iterations=args.profile_iterations,
        warmup=args.warmup,
        seed=args.seed,
        data_path=args.data_path,
        model_path=args.model_path,
        out_dir=args.out_dir,
        skip_concurrency=args.no_concurrency,
        skip_memory=args.no_memory,
        skip_determinism=args.no_determinism,
        skip_profile=args.no_profile,
    )


def load_sk_ids(data_path: Path) -> list[int]:
    csv_file = data_path / APPLICATION_CSV
    if not csv_file.exists():
        raise FileNotFoundError(f"Application CSV not found: {csv_file}")
    df = pl.read_csv(csv_file, columns=["SK_ID_CURR"])
    return df.get_column("SK_ID_CURR").unique().sort().to_list()


def sample_batch(sk_ids: list[int], batch_size: int, rng: random.Random) -> list[int]:
    if batch_size >= len(sk_ids):
        return rng.choices(sk_ids, k=batch_size)
    return rng.sample(sk_ids, k=batch_size)


def collect_environment(cfg: Config) -> dict:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "model_file": str(cfg.model_path),
        "data_path": str(cfg.data_path),
    }


def measure_startup(cfg: Config) -> tuple[dict, InferencePipeline, PolarsDataSource]:
    sys.stderr.write("Phase 1: Startup timing...\n")
    sys.stderr.flush()

    t0 = time.perf_counter()
    model = InferencePipeline.load(cfg.model_path)
    model_load_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    loader = PLLazyDataLoader(data_path=cfg.data_path, csv_names=SOURCE_CSV_NAME_MAP)
    source = PolarsDataSource.from_loader(loader)
    data_source_ms = (time.perf_counter() - t0) * 1000

    startup = {
        "model_load_ms": round(model_load_ms, 1),
        "data_source_ms": round(data_source_ms, 1),
        "total_ms": round(model_load_ms + data_source_ms, 1),
    }
    sys.stderr.write(
        f"  model_load={startup['model_load_ms']:.0f}ms  "
        f"data_source={startup['data_source_ms']:.0f}ms\n\n"
    )
    sys.stderr.flush()
    return startup, model, source


def run_benchmark(cfg: Config) -> dict:
    rng = random.Random(cfg.seed)
    sk_ids = load_sk_ids(cfg.data_path)
    sys.stderr.write(f"SK_ID pool: {len(sk_ids)} clients\n\n")

    # Phase 1: Startup
    startup, model, source = measure_startup(cfg)

    # Pre-sample batches for reproducibility
    batches = {bs: sample_batch(sk_ids, bs, rng) for bs in cfg.batch_sizes}

    # Phase 2: Cold start
    sys.stderr.write("Phase 2: Cold start (first prediction)...\n")
    sys.stderr.flush()
    cold_batch = batches[cfg.batch_sizes[0]]

    def cold_fn() -> object:
        return model.predict(assemble(source, set(cold_batch)))

    _, cold_ms = time_callable(cold_fn)
    sys.stderr.write(f"  cold_start={cold_ms:.0f}ms (batch={cfg.batch_sizes[0]})\n\n")
    sys.stderr.flush()

    # Phase 3+4: Batch sweep
    sys.stderr.write(f"Phase 3-4: Batch sweep (warmup={cfg.warmup}, runs={cfg.runs})...\n")
    sys.stderr.flush()

    def make_predict_fn(batch_size: int) -> Callable[[], object]:
        batch = batches[batch_size]

        def _run() -> object:
            raw_tables = assemble(source, set(batch))
            return model.predict(raw_tables)

        return _run

    sweep_results = run_batch_sweep(
        fn_factory=make_predict_fn,
        batch_sizes=cfg.batch_sizes,
        runs=cfg.runs,
        warmup=cfg.warmup,
    )
    for bs, stats in sweep_results.items():
        sys.stderr.write(
            f"  batch={bs:>5}: mean={stats['mean_ms']:>9.1f}ms  "
            f"per_pred={stats['per_prediction_ms']:>8.2f}ms  "
            f"p50={stats['p50_ms']:>8.1f}ms  p95={stats['p95_ms']:>8.1f}ms  "
            f"p99={stats['p99_ms']:>8.1f}ms  tput={stats['throughput_preds_per_sec']:>8.1f} p/s\n"
        )
    sys.stderr.write("\n")
    sys.stderr.flush()

    # Phase 5: Concurrency
    concurrency_results: dict | None = None
    if not cfg.skip_concurrency:
        sys.stderr.write(
            f"Phase 5: Concurrency sweep (workers={cfg.workers}, "
            f"tasks={cfg.concurrency_tasks}, batch=50)...\n"
        )
        sys.stderr.flush()

        def make_concurrent_fn(task_idx: int) -> Callable[[], object]:
            batch = sample_batch(sk_ids, 50, rng)

            def _run() -> object:
                raw_tables = assemble(source, set(batch))
                return model.predict(raw_tables)

            return _run

        concurrency_results = run_concurrency(
            fn_factory=make_concurrent_fn,
            workers=cfg.workers,
            tasks=cfg.concurrency_tasks,
            batch_size=50,
        )
        for w, stats in concurrency_results.items():
            sys.stderr.write(
                f"  workers={w:>2}: tput={stats['throughput_preds_per_sec']:>8.1f} p/s  "
                f"p50={stats['p50_ms']:>8.1f}ms  p95={stats['p95_ms']:>8.1f}ms  "
                f"wall={stats['wall_time_s']:.2f}s\n"
            )
        sys.stderr.write("\n")
        sys.stderr.flush()

    # Phase 6: Memory growth
    memory_results: dict | None = None
    if not cfg.skip_memory:
        sys.stderr.write(
            f"Phase 6: Memory growth ({cfg.memory_predictions} preds, "
            f"sample every {cfg.memory_sample_every})...\n"
        )
        sys.stderr.flush()
        mem_batch = batches[1]

        def mem_fn() -> object:
            raw_tables = assemble(source, set(mem_batch))
            return model.predict(raw_tables)

        memory_results = run_memory_growth(
            fn=mem_fn,
            total_predictions=cfg.memory_predictions,
            sample_every=cfg.memory_sample_every,
        )
        delta_mb = cast(float, memory_results["final_rss_mb"]) - cast(
            float, memory_results["initial_rss_mb"]
        )
        sys.stderr.write(
            f"  initial={memory_results['initial_rss_mb']:.1f}MB  "
            f"final={memory_results['final_rss_mb']:.1f}MB  "
            f"delta={delta_mb:.1f}MB\n\n"
        )
        sys.stderr.flush()

    # Phase 7: Determinism
    determinism_results: dict | None = None
    if not cfg.skip_determinism:
        sys.stderr.write(f"Phase 7: Determinism check ({cfg.determinism_runs} runs)...\n")
        sys.stderr.flush()
        det_batch = batches[1]

        def det_fn() -> list[float]:
            raw_tables = assemble(source, set(det_batch))
            _, probas = model.predict(raw_tables)
            return probas.tolist()

        determinism_results = run_determinism(fn=det_fn, runs=cfg.determinism_runs)
        sys.stderr.write(f"  probability_std={determinism_results['probability_std']:.8f}\n\n")
        sys.stderr.flush()

    # Phase 8: Profiling
    profile_info: dict | None = None
    if not cfg.skip_profile:
        sys.stderr.write(
            f"Phase 8: Profiling (pyinstrument, {cfg.profile_iterations} iterations)...\n"
        )
        sys.stderr.flush()
        profile_batch = batches.get(50, batches[cfg.batch_sizes[0]])
        raw_tables_profile = assemble(source, set(profile_batch))

        def profile_fn() -> object:
            return model.predict(raw_tables_profile)

        profile_info = profile_predict(
            predict_fn=profile_fn,
            iterations=cfg.profile_iterations,
            output_path=cfg.out_dir / f"profile_predict_{cfg.name}",
        )
        sys.stderr.write(f"  HTML: {profile_info['html_path']}\n")
        sys.stderr.write(f"  Text: {profile_info['text_path']}\n\n")
        sys.stderr.flush()

    return {
        "name": cfg.name,
        "script": "bench_predict",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "environment": collect_environment(cfg),
        "startup": startup,
        "cold_start_ms": round(cold_ms, 1),
        "batch_sweep": sweep_results,
        "concurrency": concurrency_results,
        "memory_growth": memory_results,
        "determinism": determinism_results,
        "peak_rss_mb": peak_rss_mb(),
        "profile": profile_info,
    }


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    cfg = parse_args()
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    sys.stderr.write(
        f"Benchmark /predict → name={cfg.name} | runs={cfg.runs} | "
        f"batch_sizes={cfg.batch_sizes}\n\n"
    )
    sys.stderr.flush()

    report = run_benchmark(cfg)

    out_json = cfg.out_dir / f"predict_{cfg.name}.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    sys.stderr.write(f"Results saved: {out_json}\n")
    sys.stderr.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
