#!/usr/bin/env python3
"""HTTP amortization benchmark — /predict batch=N vs /predict/rows ×N concurrent.

Compares two real-world strategies for scoring N clients:

1. **predict_batch** — 1 POST /predict with N sk_ids (server loads all 7 CSV tables)
2. **rows_concurrent** — N POST /predict/rows, each with 1 client's full 7-table data,
   sent concurrently with W workers (simulates N dashboard users clicking "Score")

Fairness: /predict/rows sends ALL 7 tables per client (application + bureau +
bureau_balance + previous_application + pos_cash_balance + installments +
credit_card_balance), matching what the DataSource loads for /predict.

Requires a running API instance::

    DATA_SOURCE=csv uv run uvicorn credit_risk_server.api.main:app --host 0.0.0.0

Usage::

    uv run python scripts/bench_amortization_http.py --name amortization
    uv run python scripts/bench_amortization_http.py --batch-sizes 1,5,50,250 \\
        --workers 1,8 --runs 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx
import polars as pl

from credit_risk_server.core.config import PROJECT_ROOT, api_settings

DEFAULT_OUT_DIR = PROJECT_ROOT / "docs" / "benchmark"
APPLICATION_CSV = "application_test.csv"
SOURCE_CSV_NAME_MAP = {
    "application": "application_test.csv",
    "bureau": "bureau.csv",
    "bureau_balance": "bureau_balance.csv",
    "previous_application": "previous_application.csv",
    "pos_cash_balance": "POS_CASH_balance.csv",
    "installments": "installments_payments.csv",
    "credit_card_balance": "credit_card_balance.csv",
}

TABLES_WITH_SK_ID_CURR = (
    "application",
    "bureau",
    "previous_application",
    "pos_cash_balance",
    "installments",
    "credit_card_balance",
)

logger_name = "bench_amortization_http"


@dataclass(frozen=True)
class Config:
    name: str
    url: str
    batch_sizes: list[int]
    workers: list[int]
    runs: int
    warmup: int
    timeout: float
    data_path: Path
    out_dir: Path
    seed: int


def parse_args() -> Config:
    p = argparse.ArgumentParser(
        description="HTTP amortization benchmark — /predict batch vs /predict/rows concurrent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--name", default="amortization", help="Run name (used in output filenames)")
    p.add_argument("--url", default="http://localhost:8000", help="API base URL")
    p.add_argument(
        "--batch-sizes",
        type=str,
        default="1,5,10,25,50,100,250",
        help="Comma-separated N values (number of clients to score)",
    )
    p.add_argument(
        "--workers",
        type=str,
        default="1,4,8",
        help="Comma-separated concurrency levels for /predict/rows",
    )
    p.add_argument("--runs", type=int, default=3, help="Timed runs per measurement")
    p.add_argument("--warmup", type=int, default=1, help="Warmup runs discarded")
    p.add_argument("--timeout", type=float, default=120.0, help="HTTP timeout per request (s)")
    p.add_argument(
        "--data-path",
        type=Path,
        default=api_settings.data_path,
        help="CSV data directory",
    )
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory")
    p.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = p.parse_args()

    return Config(
        name=args.name,
        url=args.url.rstrip("/"),
        batch_sizes=[int(b) for b in args.batch_sizes.split(",")],
        workers=[int(w) for w in args.workers.split(",")],
        runs=args.runs,
        warmup=args.warmup,
        timeout=args.timeout,
        data_path=args.data_path,
        out_dir=args.out_dir,
        seed=args.seed,
    )


def collect_environment() -> dict:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
    }


def load_client_data(data_path: Path) -> tuple[list[int], dict[int, dict[str, list[dict]]]]:
    """Load all 7 CSVs, build per-client lookup of row dicts for /predict/rows.

    Returns:
        sk_ids: list of all SK_ID_CURR values in application_test.csv.
        client_data: {sk_id: {table_name: [row_dict, ...]}} for all 7 tables.
    """
    sys.stderr.write("Loading 7 CSV tables and building per-client data...\n")
    sys.stderr.flush()
    t0 = time.perf_counter()

    app_df = pl.read_csv(data_path / SOURCE_CSV_NAME_MAP["application"])
    sk_ids = app_df.get_column("SK_ID_CURR").unique().sort().to_list()
    client_data: dict[int, dict[str, list[dict]]] = {sk_id: {"application": []} for sk_id in sk_ids}

    for sk_id, row in zip(sk_ids, app_df.to_dicts(), strict=True):
        client_data[sk_id]["application"] = [row]

    del app_df

    for table_name in TABLES_WITH_SK_ID_CURR:
        if table_name == "application":
            continue
        csv_name = SOURCE_CSV_NAME_MAP[table_name]
        csv_path = data_path / csv_name
        if not csv_path.exists():
            sys.stderr.write(f"  WARNING: {csv_name} not found, skipping {table_name}\n")
            sys.stderr.flush()
            continue
        df = pl.read_csv(csv_path)
        col = "SK_ID_CURR"
        grouped = df.group_by(col).agg(pl.all())
        for row in grouped.to_dicts():
            sk_id = row[col]
            if sk_id not in client_data:
                continue
            keys = [k for k in row if k != col]
            if not keys:
                continue
            n = len(row[keys[0]])
            sub_rows = [{**{col: sk_id}, **{k: row[k][i] for k in keys}} for i in range(n)]
            if sub_rows:
                client_data[sk_id][table_name] = sub_rows
        del df
        sys.stderr.write(f"  loaded {table_name}\n")
        sys.stderr.flush()

    bb_csv = data_path / SOURCE_CSV_NAME_MAP["bureau_balance"]
    if bb_csv.exists():
        bb_df = pl.read_csv(bb_csv)
        bureau_df = pl.read_csv(
            data_path / SOURCE_CSV_NAME_MAP["bureau"],
            columns=["SK_ID_CURR", "SK_ID_BUREAU"],
        )
        bb_joined = bb_df.join(bureau_df, on="SK_ID_BUREAU", how="inner")
        grouped = bb_joined.group_by("SK_ID_CURR").agg(pl.all())
        for row in grouped.to_dicts():
            sk_id = row["SK_ID_CURR"]
            if sk_id not in client_data:
                continue
            keys = [k for k in row if k != "SK_ID_CURR"]
            if not keys:
                continue
            n = len(row[keys[0]])
            sub_rows = [{"SK_ID_CURR": sk_id, **{k: row[k][i] for k in keys}} for i in range(n)]
            if sub_rows:
                client_data[sk_id]["bureau_balance"] = sub_rows
        del bb_df, bureau_df, bb_joined
        sys.stderr.write("  loaded bureau_balance (joined with bureau)\n")
        sys.stderr.flush()

    elapsed = time.perf_counter() - t0
    total_rows = sum(len(rows) for client in client_data.values() for rows in client.values())
    sys.stderr.write(
        f"  {len(sk_ids)} clients, {total_rows} total rows across 7 tables ({elapsed:.1f}s)\n\n"
    )
    sys.stderr.flush()
    return sk_ids, client_data


def build_rows_body(client_data: dict[int, dict[str, list[dict]]], sk_id: int) -> dict:
    """Build /predict/rows request body with all 7 tables for one client."""
    data = client_data[sk_id]
    body: dict[str, list[dict]] = {}
    for table_name in (
        "application",
        "bureau",
        "bureau_balance",
        "previous_application",
        "pos_cash_balance",
        "installments",
        "credit_card_balance",
    ):
        if table_name in data and data[table_name]:
            body[table_name] = data[table_name]
    return body


async def health_check(client: httpx.AsyncClient) -> bool:
    try:
        resp = await client.get("/health")
        return resp.status_code == 200
    except httpx.RequestError:
        return False


async def validate_clients(
    client: httpx.AsyncClient,
    sk_ids: list[int],
    client_data: dict[int, dict[str, list[dict]]],
    sample_size: int = 200,
) -> list[int]:
    """Pre-validate clients by sending /predict/rows to a sample, return valid sk_ids."""
    import random as rng_module

    sample = rng_module.Random(42).sample(sk_ids, k=min(sample_size, len(sk_ids)))
    sem = asyncio.Semaphore(8)

    async def check_one(sk_id: int) -> int | None:
        body = build_rows_body(client_data, sk_id)
        async with sem:
            resp = await client.post("/predict/rows", json=body)
            return sk_id if resp.status_code == 200 else None

    sys.stderr.write(f"Pre-validating {len(sample)} sample clients...\n")
    sys.stderr.flush()
    results = await asyncio.gather(*[check_one(sk) for sk in sample])
    valid = [sk for sk in results if sk is not None]
    sys.stderr.write(f"  {len(valid)}/{len(sample)} clients OK\n\n")
    sys.stderr.flush()
    return valid


async def measure_predict_batch(
    client: httpx.AsyncClient,
    sk_ids_batch: list[int],
    runs: int,
    warmup: int,
) -> dict:
    """Measure POST /predict with N sk_ids — 1 request per run."""
    body = {"sk_ids": sk_ids_batch}
    for _ in range(warmup):
        resp = await client.post("/predict", json=body)
        resp.raise_for_status()

    latencies: list[float] = []
    for _ in range(runs):
        start = time.perf_counter()
        resp = await client.post("/predict", json=body)
        elapsed_ms = (time.perf_counter() - start) * 1000
        resp.raise_for_status()
        latencies.append(elapsed_ms)

    return {
        "mean_ms": round(sum(latencies) / len(latencies), 1),
        "min_ms": round(min(latencies), 1),
        "max_ms": round(max(latencies), 1),
        "n_runs": len(latencies),
    }


async def measure_rows_concurrent(
    client: httpx.AsyncClient,
    bodies: list[dict],
    concurrency: int,
    runs: int,
    warmup: int,
) -> dict:
    """Measure N concurrent POST /predict/rows (batch=1, 7-table body)."""
    sem = asyncio.Semaphore(concurrency)

    async def post_one(body: dict) -> httpx.Response:
        async with sem:
            return await client.post("/predict/rows", json=body)

    for _ in range(warmup):
        await asyncio.gather(*[post_one(b) for b in bodies[: max(concurrency, 1)]])

    latencies: list[float] = []
    errors: int = 0
    for _ in range(runs):
        start = time.perf_counter()
        responses = await asyncio.gather(*[post_one(b) for b in bodies])
        elapsed_ms = (time.perf_counter() - start) * 1000
        for r in responses:
            if r.status_code != 200:
                errors += 1
        latencies.append(elapsed_ms)

    n_preds = len(bodies)
    mean_ms = sum(latencies) / len(latencies)
    return {
        "mean_ms": round(mean_ms, 1),
        "min_ms": round(min(latencies), 1),
        "max_ms": round(max(latencies), 1),
        "n_runs": len(latencies),
        "n_preds": n_preds,
        "errors": errors,
        "throughput_preds_per_sec": round(n_preds / (mean_ms / 1000), 1) if mean_ms > 0 else 0,
    }


async def run_benchmark(cfg: Config) -> dict:
    rng = random.Random(cfg.seed)
    sk_ids, client_data = load_client_data(cfg.data_path)
    sys.stderr.write(f"SK_ID pool: {len(sk_ids)} clients\n\n")
    sys.stderr.flush()

    limits = httpx.Limits(
        max_connections=max(cfg.workers) * 2,
        max_keepalive_connections=max(cfg.workers),
    )
    async with httpx.AsyncClient(
        base_url=cfg.url,
        timeout=cfg.timeout,
        limits=limits,
    ) as client:
        sys.stderr.write("Health check...\n")
        sys.stderr.flush()
        if not await health_check(client):
            sys.stderr.write(f"ERROR: API not reachable at {cfg.url}/health\n")
            sys.stderr.flush()
            return {}
        sys.stderr.write("  OK\n\n")
        sys.stderr.flush()

        sys.stderr.write("Warmup: 1 POST /predict (triggers CSV cold start on server)...\n")
        sys.stderr.flush()
        warmup_batch = rng.sample(sk_ids, k=min(50, len(sk_ids)))
        t0 = time.perf_counter()
        resp = await client.post("/predict", json={"sk_ids": warmup_batch})
        cold_ms = (time.perf_counter() - t0) * 1000
        resp.raise_for_status()
        sys.stderr.write(f"  /predict cold start: {cold_ms:.0f}ms (batch=50)\n")
        sys.stderr.flush()

        warmup_body = build_rows_body(client_data, sk_ids[0])
        resp = await client.post("/predict/rows", json=warmup_body)
        resp.raise_for_status()
        sys.stderr.write("  /predict/rows warmup OK\n\n")
        sys.stderr.flush()

        valid_sk_ids = await validate_clients(client, sk_ids, client_data, sample_size=500)
        if len(valid_sk_ids) < max(cfg.batch_sizes):
            sys.stderr.write(
                f"  WARNING: only {len(valid_sk_ids)} valid clients, "
                f"need {max(cfg.batch_sizes)} — reducing batch sizes\n\n"
            )
            sys.stderr.flush()

        predict_batch_results: dict[str, dict] = {}
        rows_concurrent_results: dict[str, dict[str, dict]] = {}

        for n in cfg.batch_sizes:
            sys.stderr.write(f"--- N={n} ---\n")
            sys.stderr.flush()

            pool = valid_sk_ids if len(valid_sk_ids) >= n else sk_ids
            batch_sk_ids = rng.choices(pool, k=n) if n >= len(pool) else rng.sample(pool, k=n)

            sys.stderr.write("  predict_batch...")
            sys.stderr.flush()
            t0 = time.perf_counter()
            predict_batch_results[str(n)] = await measure_predict_batch(
                client, batch_sk_ids, cfg.runs, warmup=0
            )
            sys.stderr.write(
                f" {predict_batch_results[str(n)]['mean_ms']:.0f}ms "
                f"({time.perf_counter() - t0:.1f}s total)\n"
            )
            sys.stderr.flush()

            rows_bodies = [build_rows_body(client_data, sk_id) for sk_id in batch_sk_ids]

            rows_concurrent_results[str(n)] = {}
            for w in cfg.workers:
                sys.stderr.write(f"  rows_concurrent W={w}...")
                sys.stderr.flush()
                t0 = time.perf_counter()
                rows_concurrent_results[str(n)][str(w)] = await measure_rows_concurrent(
                    client, rows_bodies, concurrency=w, runs=cfg.runs, warmup=0
                )
                stats = rows_concurrent_results[str(n)][str(w)]
                sys.stderr.write(
                    f" {stats['mean_ms']:.0f}ms "
                    f"({stats['throughput_preds_per_sec']:.1f} p/s) "
                    f"({time.perf_counter() - t0:.1f}s total)\n"
                )
                sys.stderr.flush()

            sys.stderr.write("\n")
            sys.stderr.flush()

    return {
        "name": cfg.name,
        "script": "bench_amortization_http",
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "environment": collect_environment(),
        "url": cfg.url,
        "cold_start_ms": round(cold_ms, 1),
        "predict_batch": predict_batch_results,
        "rows_concurrent": rows_concurrent_results,
    }


def print_comparison_table(report: dict, workers: list[int], batch_sizes: list[int]) -> None:
    sys.stderr.write("\n")
    sys.stderr.write("=" * 120 + "\n")
    sys.stderr.write(
        "HTTP Amortization — /predict batch=N vs /predict/rows ×N concurrent (all 7 tables)\n"
    )
    sys.stderr.write("=" * 120 + "\n\n")

    header = f"{'N':>5} | {'predict_batch':>14}"
    for w in workers:
        header += f" | {'rows W=' + str(w):>14}"
    header += f" | {'best_rows':>14} | {'winner':>10}"
    sys.stderr.write(header + "\n")
    sys.stderr.write("-" * len(header) + "\n")

    for n in batch_sizes:
        n_str = str(n)
        if n_str not in report.get("predict_batch", {}):
            continue

        pb = report["predict_batch"][n_str]
        pb_ms = pb["mean_ms"]

        row = f"{n:>5} | {pb_ms:>10.0f} ms"
        best_rows_ms = float("inf")
        for w in workers:
            w_str = str(w)
            rc = report.get("rows_concurrent", {}).get(n_str, {}).get(w_str)
            if rc:
                ms = rc["mean_ms"]
                if ms < best_rows_ms:
                    best_rows_ms = ms
                row += f" | {ms:>10.0f} ms"
            else:
                row += f" | {'n/a':>14}"

        if best_rows_ms == float("inf"):
            best_rows_str = "n/a"
            winner = "n/a"
        else:
            best_rows_str = f"{best_rows_ms:.0f} ms"
            winner = "rows" if best_rows_ms < pb_ms else "predict"

        row += f" | {best_rows_str:>14} | {winner:>10}"
        sys.stderr.write(row + "\n")

    sys.stderr.write("\n")
    sys.stderr.write("Crossover analysis:\n")
    for w in workers:
        w_str = str(w)
        crossover_n = None
        for n in batch_sizes:
            n_str = str(n)
            pb = report.get("predict_batch", {}).get(n_str)
            rc = report.get("rows_concurrent", {}).get(n_str, {}).get(w_str)
            if pb and rc and rc["mean_ms"] > pb["mean_ms"]:
                crossover_n = n
                break
        if crossover_n is not None:
            sys.stderr.write(
                f"  vs W={w}: /predict batch wins at N>={crossover_n} "
                f"(/predict {report['predict_batch'][str(crossover_n)]['mean_ms']:.0f}ms"
                f" vs rows {report['rows_concurrent'][str(crossover_n)][w_str]['mean_ms']:.0f}ms)\n"
            )
        else:
            sys.stderr.write(f"  vs W={w}: /predict batch never wins in tested range\n")
    sys.stderr.write("\n")
    sys.stderr.flush()


def main() -> int:
    cfg = parse_args()
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    sys.stderr.write(
        f"HTTP Amortization Benchmark → {cfg.url} | "
        f"name={cfg.name} | batch_sizes={cfg.batch_sizes} | "
        f"workers={cfg.workers} | runs={cfg.runs}\n\n"
    )
    sys.stderr.flush()

    report = asyncio.run(run_benchmark(cfg))
    if not report:
        return 1

    out_json = cfg.out_dir / f"amortization_http_{cfg.name}.json"
    out_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    sys.stderr.write(f"Results saved: {out_json}\n")
    sys.stderr.flush()

    print_comparison_table(report, cfg.workers, cfg.batch_sizes)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
