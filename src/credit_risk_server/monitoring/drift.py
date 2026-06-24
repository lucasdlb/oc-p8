"""Data drift detection using Evidently AI.

Computes PSI for scores + selected raw application features every interval,
produces an Evidently Snapshot and writes it to a local Workspace that the
``evidently-ui`` container serves as a web dashboard.

No Prometheus coupling — drift lives in Evidently's own UI (D-02b).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from evidently import Report
from evidently.core.report import Snapshot
from evidently.metrics import DriftedColumnsCount, QuantileValue, ValueDrift
from evidently.sdk.models import PanelMetric
from evidently.sdk.panels import counter_panel, line_plot_panel
from evidently.ui.workspace import Workspace

logger = logging.getLogger(__name__)

DRIFT_FEATURES: tuple[str, ...] = (
    # numeric
    "AMT_CREDIT",
    "AMT_INCOME_TOTAL",
    "AMT_ANNUITY",
    "AMT_GOODS_PRICE",
    "DAYS_BIRTH",
    "DAYS_EMPLOYED",
    "DAYS_REGISTRATION",
    "EXT_SOURCE_1",
    "EXT_SOURCE_2",
    "EXT_SOURCE_3",
    "REGION_RATING_CLIENT",
    # categorical
    "CODE_GENDER",
    "NAME_INCOME_TYPE",
)
"""Top-N raw ``application`` columns monitored for data drift (D-20)."""

_PROJECT_NAME = "credit_risk_drift"

_M_VALUE_DRIFT = "evidently:metric_v2:ValueDrift"
_M_DRIFTED_COUNT = "evidently:metric_v2:DriftedColumnsCount"
_M_QUANTILE = "evidently:metric_v2:QuantileValue"

_SCORE_QUANTILES = (0.1, 0.5, 0.9)


def _build_report_metrics(features: Iterable[str], psi_threshold: float) -> list[Any]:
    """Build the Evidently metric list reused for every ``compute()``.

    Includes PSI ValueDrift for ``score`` and each monitored feature,
    DriftedColumnsCount (share-based, PSI), and QuantileValue for score
    at p10/p50/p90 (feeds the distribution panel).
    """
    metrics: list[Any] = [
        ValueDrift(column="score", method="psi", threshold=psi_threshold),  # ty: ignore[missing-argument]
        DriftedColumnsCount(drift_share=0.3, method="psi", threshold=psi_threshold),  # ty: ignore[missing-argument]
    ]
    for f in features:
        metrics.append(ValueDrift(column=f, method="psi", threshold=psi_threshold))  # ty: ignore[missing-argument]
    for q in _SCORE_QUANTILES:
        metrics.append(QuantileValue(column="score", quantile=q))  # ty: ignore[missing-argument]
    return metrics


def _extract_results(snapshot: Snapshot, features: tuple[str, ...]) -> dict[str, Any]:
    """Extract a summary dict from an Evidently Snapshot's metric_results."""
    result: dict[str, Any] = {}
    for mr in snapshot.metric_results.values():
        name = mr.display_name
        if name == "Count of Drifted Columns":
            count_obj = getattr(mr, "count", None)
            share_obj = getattr(mr, "share", None)
            result["drifted_count"] = int(getattr(count_obj, "value", 0)) if count_obj else 0
            result["drifted_share"] = float(getattr(share_obj, "value", 0.0)) if share_obj else 0.0
        elif name.startswith("Value drift for "):
            col = name.removeprefix("Value drift for ")
            value = getattr(mr, "value", None)
            if col == "score":
                result["score_psi"] = float(value) if value is not None else None
            else:
                result.setdefault("feature_psi", {})[col] = (
                    float(value) if value is not None else None
                )
    return result


class DriftMonitor:
    """Buffers live predictions and computes drift snapshots via Evidently.

    The monitor accumulates ``(score, application_row)`` pairs in a fixed-size
    ring buffer.  When ``compute()`` is called (either manually or via the
    periodic asyncio task) the current window is compared against the
    reference dataset using Evidently's PSI-based drift metrics, and the
    resulting :class:`~evidently.core.report.Snapshot` is written to the
    shared :class:`~evidently.ui.workspace.Workspace`.
    """

    def __init__(
        self,
        reference_df: pd.DataFrame,
        features: tuple[str, ...],
        workspace: Workspace,
        project_id: str | uuid.UUID,
        *,
        buffer_size: int = 5000,
        min_samples: int = 50,
        psi_threshold: float = 0.25,
    ) -> None:
        self._reference = reference_df
        self._features = features
        self._workspace = workspace
        self._project_id = project_id
        self._buffer: deque[dict[str, Any]] = deque(maxlen=buffer_size)
        self._min_samples = min_samples
        self._psi_threshold = psi_threshold
        self._metrics = _build_report_metrics(features, psi_threshold)
        self._task: asyncio.Task[None] | None = None

    @property
    def buffer_count(self) -> int:
        """Number of predictions currently in the rolling buffer."""
        return len(self._buffer)

    def record(self, score: float, application_row: Mapping[str, Any]) -> None:
        """Append a prediction to the rolling buffer.

        Only the monitored features are extracted from *application_row*;
        missing keys become ``None`` (NaN in the DataFrame).
        """
        entry: dict[str, Any] = {"score": score}
        for f in self._features:
            entry[f] = application_row.get(f)
        self._buffer.append(entry)

    def compute(self) -> dict[str, Any]:
        """Run drift detection and write the Snapshot to the workspace.

        Returns an empty dict when the buffer has fewer than ``min_samples``
        entries.  Otherwise returns a summary dict with drifted-count,
        score PSI, and per-feature PSI values.
        """
        if len(self._buffer) < self._min_samples:
            logger.debug(
                "drift compute skipped — insufficient samples",
                extra={"buffer": len(self._buffer), "min": self._min_samples},
            )
            return {}

        current = pd.DataFrame(list(self._buffer))
        report = Report(metrics=self._metrics)
        snapshot = report.run(
            current_data=current,
            reference_data=self._reference,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self._workspace.add_run(self._project_id, snapshot)

        result = _extract_results(snapshot, self._features)
        logger.info("drift snapshot written", extra=result)
        return result

    def start_periodic_compute(self, interval_seconds: int = 60) -> asyncio.Task[None]:
        """Start a background asyncio task that calls ``compute()`` periodically."""

        async def _loop() -> None:
            while True:
                await asyncio.sleep(interval_seconds)
                try:
                    await asyncio.to_thread(self.compute)
                except Exception:
                    logger.error("periodic drift compute failed", exc_info=True)

        self._task = asyncio.create_task(_loop(), name="drift-periodic-compute")
        return self._task

    def stop_periodic_compute(self) -> None:
        """Cancel the background periodic-compute task if running."""
        if self._task is not None:
            self._task.cancel()
            self._task = None


def init_workspace(workspace_path: Path) -> tuple[Workspace, Any]:
    """Create or open an Evidently Workspace and ensure the drift Project exists.

    Creates the project with four dashboard panels (drifted-columns counter,
    score PSI, feature PSI, score quantiles).  Idempotent — if the project
    already exists it is reused as-is (D-02b).
    """
    workspace_path.mkdir(parents=True, exist_ok=True)
    workspace = Workspace.create(str(workspace_path))

    projects = workspace.list_projects()
    existing = [p for p in projects if p.name == _PROJECT_NAME]
    if existing:
        return workspace, existing[0]

    project = workspace.create_project(_PROJECT_NAME)
    project.description = "Credit-risk data drift monitoring (PSI)"

    project.dashboard.add_panel(
        counter_panel(
            title="Drifted Columns Count",
            size="half",
            values=[
                PanelMetric(
                    legend="count",
                    metric=_M_DRIFTED_COUNT,
                    metric_labels={},
                ),
            ],
            aggregation="last",
        )
    )

    project.dashboard.add_panel(
        line_plot_panel(
            title="Score PSI Over Time",
            values=[
                PanelMetric(
                    legend="score",
                    metric=_M_VALUE_DRIFT,
                    metric_labels={"column": "score"},
                ),
            ],
        )
    )

    feature_values = [
        PanelMetric(
            legend=f,
            metric=_M_VALUE_DRIFT,
            metric_labels={"column": f},
        )
        for f in DRIFT_FEATURES
    ]
    project.dashboard.add_panel(
        line_plot_panel(
            title="Feature PSI Over Time",
            values=feature_values,
        )
    )

    quantile_values = [
        PanelMetric(
            legend=f"p{int(q * 100)}",
            metric=_M_QUANTILE,
            metric_labels={"column": "score", "quantile": str(q)},
        )
        for q in _SCORE_QUANTILES
    ]
    project.dashboard.add_panel(
        line_plot_panel(
            title="Score Distribution (quantiles)",
            values=quantile_values,
        )
    )

    project.save()
    return workspace, project


def load_reference(
    path: Path,
    workspace_path: Path,
    *,
    buffer_size: int = 5000,
    min_samples: int = 50,
    psi_threshold: float = 0.25,
) -> DriftMonitor | None:
    """Load reference scores + features and return a :class:`DriftMonitor`.

    Reads ``scores.parquet`` and ``features.parquet`` from *path*, merges on
    ``SK_ID_CURR``, determines which DRIFT_FEATURES are available, creates
    the Evidently workspace/project/dashboard via :func:`init_workspace`,
    and returns a configured DriftMonitor.

    Returns ``None`` when the reference files are missing (logs at INFO).
    """
    scores_path = path / "scores.parquet"
    features_path = path / "features.parquet"
    if not scores_path.exists() or not features_path.exists():
        logger.info(
            "drift reference not found — drift monitoring disabled",
            extra={"path": str(path)},
        )
        return None

    scores_df = pd.read_parquet(scores_path)
    features_df = pd.read_parquet(features_path)

    available = [c for c in DRIFT_FEATURES if c in features_df.columns]
    missing = [c for c in DRIFT_FEATURES if c not in features_df.columns]
    if missing:
        logger.warning("reference features missing", extra={"missing": missing})

    merged = scores_df.merge(features_df, on="SK_ID_CURR", how="inner")
    reference = merged[["score", *available]]

    workspace, project = init_workspace(workspace_path)

    logger.info(
        "drift reference loaded",
        extra={
            "reference_rows": len(reference),
            "features": available,
            "workspace": str(workspace_path),
        },
    )

    return DriftMonitor(
        reference_df=reference,
        features=tuple(available),
        workspace=workspace,
        project_id=project.id,
        buffer_size=buffer_size,
        min_samples=min_samples,
        psi_threshold=psi_threshold,
    )
