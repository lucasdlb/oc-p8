"""Benchmark primitives — shared measurement utilities for benchmark scripts.

Provides reusable functions for latency statistics, memory tracking, profiling,
batch sweeps, and concurrency tests. Used by ``scripts/bench_predict.py`` and
``scripts/bench_predict_rows.py`` to keep orchestration logic thin.

All functions are pure (no I/O side effects except ``profile_predict`` which
writes an HTML file) so they can be unit-tested in isolation.
"""

from __future__ import annotations

import resource
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import mean, pstdev

from pyinstrument import Profiler


def compute_stats(latencies_ms: list[float]) -> dict[str, float]:
    """Compute latency statistics from a list of durations in milliseconds.

    Args:
        latencies_ms: List of per-run latencies in milliseconds.

    Returns:
        Dict with ``mean_ms``, ``p50_ms``, ``p95_ms``, ``p99_ms``, ``std_ms``,
        and ``n``. Returns empty stats if the list is empty.
    """
    if not latencies_ms:
        return {"mean_ms": 0.0, "p50_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0, "std_ms": 0.0, "n": 0}

    n = len(latencies_ms)
    sorted_lat = sorted(latencies_ms)
    p50 = sorted_lat[n // 2]
    p95 = sorted_lat[min(int(n * 0.95), n - 1)]
    p99 = sorted_lat[min(int(n * 0.99), n - 1)]
    std = pstdev(latencies_ms) if n > 1 else 0.0

    return {
        "mean_ms": round(mean(latencies_ms), 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "std_ms": round(std, 2),
        "n": n,
    }


def peak_rss_mb() -> float:
    """Return process peak RSS in megabytes (Linux: ``ru_maxrss`` is in KB)."""
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 2)


def throughput(batch_size: int, mean_latency_s: float) -> float:
    """Compute throughput in predictions per second.

    Args:
        batch_size: Number of predictions per run.
        mean_latency_s: Mean latency in seconds.

    Returns:
        Predictions per second, or 0.0 if latency is zero.
    """
    if mean_latency_s <= 0:
        return 0.0
    return round(batch_size / mean_latency_s, 1)


def time_callable(fn: Callable[[], object]) -> tuple[object, float]:
    """Execute *fn* and return (result, elapsed_ms) via ``perf_counter``."""
    start = time.perf_counter()
    result = fn()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return result, elapsed_ms


def run_batch_sweep(
    fn_factory: Callable[[int], Callable[[], object]],
    batch_sizes: list[int],
    runs: int,
    warmup: int = 3,
) -> dict[str, dict]:
    """Run a latency sweep across batch sizes.

    Args:
        fn_factory: Returns a callable that performs one benchmark run for the
            given batch size. Called fresh each time so the factory can prepare
            inputs of the right size.
        batch_sizes: Batch sizes to sweep.
        runs: Number of timed runs per batch size (after warmup).
        warmup: Discarded runs to prime caches / lazy scans.

    Returns:
        ``{str(batch_size): {stats..., throughput_preds_per_sec, per_prediction_ms,
        efficiency_vs_single}}`` where ``per_prediction_ms`` is the amortized
        cost per prediction and ``efficiency_vs_single`` is the ratio relative
        to batch=1 (<1.0 means batching is cheaper per prediction).
    """
    results: dict[str, dict] = {}
    for bs in batch_sizes:
        fn = fn_factory(bs)
        for _ in range(warmup):
            fn()
        latencies: list[float] = []
        for _ in range(runs):
            _, ms = time_callable(fn)
            latencies.append(ms)
        stats = compute_stats(latencies)
        stats["throughput_preds_per_sec"] = throughput(bs, stats["mean_ms"] / 1000.0)
        stats["per_prediction_ms"] = round(stats["mean_ms"] / bs, 2)
        results[str(bs)] = stats

    if "1" in results:
        single_cost = results["1"]["per_prediction_ms"]
        for _bs_key, stats in results.items():
            stats["efficiency_vs_single"] = round(stats["per_prediction_ms"] / single_cost, 3)

    return results


def run_concurrency(
    fn_factory: Callable[[int], Callable[[], object]],
    workers: list[int],
    tasks: int,
    batch_size: int = 50,
) -> dict[str, dict]:
    """Run a concurrency sweep using ``ThreadPoolExecutor``.

    Each worker submits ``tasks`` total calls to a thread pool of varying size.
    Measures wall-clock time for all tasks to complete, then derives throughput
    and per-task latency stats.

    Args:
        fn_factory: Returns a callable for the given task index (0-based).
            Allows each task to use different inputs if desired.
        workers: Thread pool sizes to sweep.
        tasks: Total number of tasks to submit per worker config.
        batch_size: Predictions per task (for throughput calculation).

    Returns:
        ``{str(workers): {throughput, p50_ms, p95_ms, n}}``
    """
    results: dict[str, dict] = {}
    for w in workers:
        latencies: list[float] = []
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=w) as pool:
            futures = [pool.submit(fn_factory(i)) for i in range(tasks)]
            for future in as_completed(futures):
                _, ms = time_callable(lambda f=future: f.result())
                latencies.append(ms)
        wall_s = time.perf_counter() - start
        stats = compute_stats(latencies)
        stats["throughput_preds_per_sec"] = throughput(tasks * batch_size, wall_s)
        stats["wall_time_s"] = round(wall_s, 3)
        results[str(w)] = stats
    return results


def run_memory_growth(
    fn: Callable[[], object],
    total_predictions: int,
    sample_every: int = 100,
) -> dict[str, object]:
    """Run *fn* repeatedly and sample peak RSS at intervals.

    Args:
        fn: Callable performing one prediction (batch_size=1 recommended).
        total_predictions: Number of sequential calls.
        sample_every: RSS sample interval.

    Returns:
        ``{initial_rss_mb, final_rss_mb, samples: [{after_n, rss_mb}]}``
    """
    initial = peak_rss_mb()
    samples: list[dict[str, object]] = [{"after_n": 0, "rss_mb": initial}]
    for i in range(1, total_predictions + 1):
        fn()
        if i % sample_every == 0:
            samples.append({"after_n": i, "rss_mb": peak_rss_mb()})
    final = peak_rss_mb()
    return {"initial_rss_mb": initial, "final_rss_mb": final, "samples": samples}


def run_determinism(
    fn: Callable[[], list[float]],
    runs: int = 50,
) -> dict[str, float]:
    """Check output determinism — same input, N runs, probability variance.

    Args:
        fn: Callable returning a list of probabilities for the same input.
        runs: Number of identical runs.

    Returns:
        ``{probability_std, n}`` — std should be ~0.0 for deterministic inference.
    """
    per_run_means: list[float] = []
    for _ in range(runs):
        probas = fn()
        per_run_means.append(mean(probas) if probas else 0.0)
    std = pstdev(per_run_means) if runs > 1 else 0.0
    return {"probability_std": round(std, 8), "n": runs}


def profile_predict(
    predict_fn: Callable[[], object],
    iterations: int,
    output_path: Path,
) -> dict[str, object]:
    """Profile *predict_fn* with pyinstrument and save HTML + text reports.

    Produces three outputs:
    - **HTML** (interactive, for browser) → ``<output_path>.html``
    - **Text call-tree** (for terminal/docs) → ``<output_path>.txt``
    - **Flat profile** (time per method) → appended to ``<output_path>.txt``

    Args:
        predict_fn: Callable that runs one ``model.predict()`` call (or equivalent).
        iterations: Number of iterations inside the profiler (enough samples).
        output_path: Base path for output files (extensions added automatically).

    Returns:
        Dict with ``html_path``, ``text_path``, ``duration_ms``, ``sample_count``.
    """
    profiler = Profiler()
    profiler.start()
    for _ in range(iterations):
        predict_fn()
    profiler.stop()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_path = output_path.with_suffix(".html")
    text_path = output_path.with_suffix(".txt")

    html_path.write_text(profiler.output_html(), encoding="utf-8")

    tree_text = profiler.output_text(color=False, show_all=False)
    flat_text = profiler.output_text(color=False, flat=True, show_all=True)
    combined = (
        "=== CALL TREE ===\n\n" + tree_text + "\n\n=== FLAT PROFILE (self time) ===\n\n" + flat_text
    )
    text_path.write_text(combined, encoding="utf-8")

    return {
        "html_path": str(html_path),
        "text_path": str(text_path),
    }
