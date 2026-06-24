#!/usr/bin/env python3
"""Traffic simulator — continuously sends requests to the Credit Risk API.

Generates realistic mixed traffic (health checks, predictions, invalid inputs)
with configurable rates and weighted endpoint distribution. Outputs structured
JSON logs to stdout for Promtail ingestion and prints live summaries to stderr.

Usage:
    python scripts/traffic_simulator.py
    python scripts/traffic_simulator.py --url http://localhost:8000 --rps 5
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from math import isclose

import httpx

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

PREDICT_ROWS_BODY = {"application": [MINIMAL_APP_ROW]}
PREDICT_BODY = {"sk_ids": [100001]}
INVALID_BODY = {"application": [{"SK_ID_CURR": "not_a_number"}]}
EMPTY_APP_BODY = {"application": []}

PATHS = [
    ("/health", "GET", None, "health"),
    ("/predict/rows", "POST", PREDICT_ROWS_BODY, "predict_rows"),
    ("/predict", "POST", PREDICT_BODY, "predict"),
    ("/predict/rows", "POST", EMPTY_APP_BODY, "predict_rows_empty"),
    ("/predict/rows", "POST", INVALID_BODY, "predict_rows_invalid"),
]


@dataclass(frozen=True)
class Config:
    url: str
    rps: float
    ratios: tuple[float, float, float, float, float]
    timeout: float
    summary_every: int


def parse_args() -> Config:
    parser = argparse.ArgumentParser(
        description="Traffic simulator for the Credit Risk API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--rps", type=float, default=2.0, help="Average requests per second")
    parser.add_argument("--health-ratio", type=float, default=0.45, help="Weight for GET /health")
    parser.add_argument(
        "--predict-rows-ratio",
        type=float,
        default=0.35,
        help="Weight for POST /predict/rows",
    )
    parser.add_argument(
        "--predict-ratio", type=float, default=0.10, help="Weight for POST /predict"
    )
    parser.add_argument(
        "--empty-ratio", type=float, default=0.05, help="Weight for empty app (422)"
    )
    parser.add_argument(
        "--invalid-ratio", type=float, default=0.05, help="Weight for malformed (422 Pydantic)"
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    parser.add_argument(
        "--summary-every", type=int, default=100, help="Print summary every N requests"
    )
    args = parser.parse_args()

    ratios = (
        args.health_ratio,
        args.predict_rows_ratio,
        args.predict_ratio,
        args.empty_ratio,
        args.invalid_ratio,
    )
    total = sum(ratios)
    if not isclose(total, 1.0, abs_tol=0.01):
        parser.error(f"Ratios must sum to ~1.0, got {total:.3f}")

    return Config(
        url=args.url.rstrip("/"),
        rps=args.rps,
        ratios=ratios,
        timeout=args.timeout,
        summary_every=args.summary_every,
    )


def pick_endpoint(cfg: Config) -> tuple[str, str, dict | None, str]:
    r = random.random()
    cumulative = 0.0
    for (path, method, body, label), weight in zip(PATHS, cfg.ratios, strict=True):
        cumulative += weight
        if r <= cumulative:
            return method, path, body, label
    fallback = PATHS[0]
    return fallback[1], fallback[0], fallback[2], fallback[3]


def log_request(
    method: str,
    endpoint: str,
    status: int,
    duration_ms: float,
    error: str | None = None,
) -> None:
    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "level": "error" if status >= 400 or error else "info",
        "method": method,
        "endpoint": endpoint,
        "status": status,
        "duration_ms": round(duration_ms, 1),
        "logger": "traffic_simulator",
    }
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
    p99 = sorted_lat[int(len(sorted_lat) * 0.99)]
    sys.stderr.write(
        f"[{count} reqs] "
        f"ok={stats['ok']} error={stats['error']} "
        f"avg={avg:.0f}ms p50={p50:.0f}ms p99={p99:.0f}ms\n"
    )
    sys.stderr.flush()


def main() -> None:
    cfg = parse_args()
    sys.stderr.write(
        f"Traffic simulator → {cfg.url} | "
        f"rps={cfg.rps} | "
        f"ratios=health:{cfg.ratios[0]:.0%} predict_rows:{cfg.ratios[1]:.0%} "
        f"predict:{cfg.ratios[2]:.0%} empty:{cfg.ratios[3]:.0%} "
        f"invalid:{cfg.ratios[4]:.0%}\n"
        f"Press Ctrl+C to stop.\n\n"
    )
    sys.stderr.flush()

    stats: dict = {"total": 0, "ok": 0, "error": 0, "latencies": []}

    with httpx.Client(base_url=cfg.url, timeout=cfg.timeout) as client:
        while True:
            d = random.expovariate(cfg.rps)
            time.sleep(d)

            method, path, body, label = pick_endpoint(cfg)
            start = time.perf_counter()

            try:
                resp = client.request(method, path, json=body)
                status = resp.status_code
                error = None
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

            log_request(method, path, status, duration_ms, error)

            if stats["total"] % cfg.summary_every == 0:
                print_summary(stats, stats["total"])
                stats["latencies"].clear()
                stats["ok"] = 0
                stats["error"] = 0


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.stderr.write("\nTraffic simulator stopped.\n")
        sys.stderr.flush()
