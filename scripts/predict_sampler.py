#!/usr/bin/env python3
"""Predict sampler — sends random SK_IDs from the test set to /predict.

Loads SK_ID_CURR values from ``application_test.csv``, samples random batches,
POSTs them to the Credit Risk API's ``/predict`` endpoint, and logs structured
JSON to stdout (Promtail-compatible) with latency summaries on stderr.

Usage::

    python scripts/predict_sampler.py
    python scripts/predict_sampler.py --url http://localhost:8000 --batch-size 100 --rps 5
    python scripts/predict_sampler.py --count 200    # stop after 200 requests
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
import polars as pl

from credit_risk_server.core.config import PROJECT_ROOT

DEFAULT_DATA_PATH = PROJECT_ROOT / "data"
APPLICATION_CSV = "application_test.csv"


@dataclass(frozen=True)
class Config:
    url: str
    batch_size: int
    rps: float
    count: int
    seed: int | None
    data_path: Path
    timeout: float
    summary_every: int


def parse_args() -> Config:
    parser = argparse.ArgumentParser(
        description="Predict sampler — random SK_IDs from the test set to /predict",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--batch-size", type=int, default=50, help="SK_IDs per /predict call")
    parser.add_argument("--rps", type=float, default=2.0, help="Average requests per second")
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="Total requests to send (0 = infinite, Ctrl+C to stop)",
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument(
        "--data-path",
        type=Path,
        default=DEFAULT_DATA_PATH,
        help="CSV data directory (contains application_test.csv)",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout in seconds")
    parser.add_argument(
        "--summary-every", type=int, default=50, help="Print summary every N requests"
    )
    args = parser.parse_args()
    return Config(
        url=args.url.rstrip("/"),
        batch_size=args.batch_size,
        rps=args.rps,
        count=args.count,
        seed=args.seed,
        data_path=args.data_path,
        timeout=args.timeout,
        summary_every=args.summary_every,
    )


def load_sk_ids(data_path: Path, csv_name: str = APPLICATION_CSV) -> list[int]:
    """Load all unique SK_ID_CURR values from the application CSV."""
    csv_file = data_path / csv_name
    if not csv_file.exists():
        raise FileNotFoundError(f"Application CSV not found: {csv_file}")
    df = pl.read_csv(csv_file, columns=["SK_ID_CURR"])
    return df.get_column("SK_ID_CURR").unique().sort().to_list()


def sample_batch(sk_ids: list[int], batch_size: int, rng: random.Random) -> list[int]:
    """Sample a random batch of SK_IDs (with replacement if batch exceeds pool)."""
    if batch_size >= len(sk_ids):
        return rng.choices(sk_ids, k=batch_size)
    return rng.sample(sk_ids, k=batch_size)


def log_request(
    status: int,
    duration_ms: float,
    batch_size: int,
    predictions: int | None,
    error: str | None = None,
) -> None:
    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "level": "error" if status >= 400 or error else "info",
        "method": "POST",
        "endpoint": "/predict",
        "status": status,
        "duration_ms": round(duration_ms, 1),
        "batch_size": batch_size,
        "logger": "predict_sampler",
    }
    if predictions is not None:
        entry["predictions"] = predictions
    if error:
        entry["error"] = error
    sys.stdout.write(json.dumps(entry, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def print_summary(stats: dict, count: int) -> None:
    latencies = stats["latencies"]
    if not latencies:
        return
    avg = sum(latencies) / len(latencies)
    sorted_lat = sorted(latencies)
    p50 = sorted_lat[len(sorted_lat) // 2]
    p99 = sorted_lat[int(len(sorted_lat) * 0.99)] if len(sorted_lat) > 1 else sorted_lat[0]
    sys.stderr.write(
        f"[{count} reqs] "
        f"ok={stats['ok']} error={stats['error']} "
        f"avg={avg:.0f}ms p50={p50:.0f}ms p99={p99:.0f}ms\n"
    )
    sys.stderr.flush()


def main() -> int:
    cfg = parse_args()
    rng = random.Random(cfg.seed)

    sk_ids: list[int] = []
    try:
        sk_ids = load_sk_ids(cfg.data_path)
    except FileNotFoundError:
        sys.stderr.write(f"Cannot load SK_IDs from {cfg.data_path / APPLICATION_CSV}\n")
        return 1
    if not sk_ids:
        sys.stderr.write("No SK_ID_CURR found in the application CSV\n")
        return 1

    duration_label = f"{cfg.count} requests" if cfg.count > 0 else "infinite (Ctrl+C to stop)"
    sys.stderr.write(
        f"Predict sampler → {cfg.url} | "
        f"pool={len(sk_ids)} SK_IDs | "
        f"batch={cfg.batch_size} | "
        f"rps={cfg.rps} | "
        f"duration={duration_label}\n"
        f"Press Ctrl+C to stop.\n\n"
    )
    sys.stderr.flush()

    stats: dict = {"total": 0, "ok": 0, "error": 0, "latencies": []}

    with httpx.Client(base_url=cfg.url, timeout=cfg.timeout) as client:
        try:
            while cfg.count == 0 or stats["total"] < cfg.count:
                d = random.expovariate(cfg.rps)
                time.sleep(d)

                batch = sample_batch(sk_ids, cfg.batch_size, rng)
                body = {"sk_ids": batch}
                start = time.perf_counter()

                predictions: int | None = None
                try:
                    resp = client.post("/predict", json=body)
                    status = resp.status_code
                    error = None
                    if 200 <= status < 300:
                        try:
                            data = resp.json()
                            predictions = len(data)
                        except (ValueError, json.JSONDecodeError):
                            pass
                except httpx.RequestError as exc:
                    status = 0
                    error = str(exc)

                duration_ms = (time.perf_counter() - start) * 1000

                stats["total"] += 1
                stats["latencies"].append(duration_ms)
                if 200 <= status < 400:
                    stats["ok"] += 1
                else:
                    stats["error"] += 1

                log_request(status, duration_ms, cfg.batch_size, predictions, error)

                if stats["total"] % cfg.summary_every == 0:
                    print_summary(stats, stats["total"])
                    stats["latencies"].clear()
                    stats["ok"] = 0
                    stats["error"] = 0
        except KeyboardInterrupt:
            pass

    sys.stderr.write(f"\nPredict sampler stopped. Total requests: {stats['total']}\n")
    sys.stderr.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
