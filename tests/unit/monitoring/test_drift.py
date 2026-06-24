"""Unit tests for drift monitoring — DriftMonitor, workspace, load_reference."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from credit_risk_server.monitoring.drift import (
    DRIFT_FEATURES,
    DriftMonitor,
    init_workspace,
    load_reference,
)

RNG = np.random.default_rng(42)
FEATURES = ("AMT_CREDIT", "DAYS_BIRTH", "CODE_GENDER")


def _make_reference_df(n: int = 200) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "score": RNG.random(n),
            "AMT_CREDIT": RNG.random(n) * 100_000,
            "DAYS_BIRTH": RNG.random(n) * -20_000,
            "CODE_GENDER": RNG.choice(["M", "F"], n),
        }
    )


def _make_monitor(
    tmp_path: Path, reference_df: pd.DataFrame | None = None, **kwargs
) -> DriftMonitor:
    reference = reference_df if reference_df is not None else _make_reference_df()
    workspace, project = init_workspace(tmp_path / "ws")
    return DriftMonitor(
        reference_df=reference,
        features=FEATURES,
        workspace=workspace,
        project_id=project.id,
        min_samples=kwargs.pop("min_samples", 10),
        **kwargs,
    )


def _fill_buffer(monitor: DriftMonitor, n: int, shift: float = 0.0) -> None:
    for _ in range(n):
        monitor.record(
            float(RNG.random() + shift),
            {
                "AMT_CREDIT": float(RNG.random() * 100_000),
                "DAYS_BIRTH": float(RNG.random() * -20_000),
                "CODE_GENDER": str(RNG.choice(["M", "F"])),
            },
        )


class TestInitWorkspace:
    def test_workspace_created(self, tmp_path: Path):
        ws, project = init_workspace(tmp_path / "ws")
        assert ws is not None
        assert project.name == "credit_risk_drift"
        projects = ws.list_projects()
        assert any(p.name == "credit_risk_drift" for p in projects)

    def test_workspace_idempotent(self, tmp_path: Path):
        ws1, proj1 = init_workspace(tmp_path / "ws")
        ws2, proj2 = init_workspace(tmp_path / "ws")
        assert proj1.id == proj2.id


class TestLoadReference:
    def test_load_reference_missing_returns_none(self, tmp_path: Path):
        result = load_reference(tmp_path / "nonexistent", tmp_path / "ws")
        assert result is None

    def test_load_reference_success(self, tmp_path: Path):
        ref_dir = tmp_path / "ref"
        ref_dir.mkdir()
        ref = _make_reference_df(100)
        scores = ref[["AMT_CREDIT"]].rename(columns={"AMT_CREDIT": "score"})
        scores.insert(0, "SK_ID_CURR", range(100))
        features = ref[["AMT_CREDIT", "DAYS_BIRTH", "CODE_GENDER"]]
        features.insert(0, "SK_ID_CURR", range(100))
        pd.DataFrame({"SK_ID_CURR": range(100), "score": ref["score"]}).to_parquet(
            ref_dir / "scores.parquet"
        )
        features.to_parquet(ref_dir / "features.parquet")

        monitor = load_reference(ref_dir, tmp_path / "ws", min_samples=10)
        assert monitor is not None
        assert monitor.buffer_count == 0


class TestRecord:
    def test_record_grows_buffer(self, tmp_path: Path):
        monitor = _make_monitor(tmp_path)
        assert monitor.buffer_count == 0
        monitor.record(0.5, {"AMT_CREDIT": 1000.0, "DAYS_BIRTH": -9000, "CODE_GENDER": "M"})
        assert monitor.buffer_count == 1
        monitor.record(0.3, {"AMT_CREDIT": 2000.0, "DAYS_BIRTH": -8000, "CODE_GENDER": "F"})
        assert monitor.buffer_count == 2

    def test_record_missing_feature_becomes_none(self, tmp_path: Path):
        monitor = _make_monitor(tmp_path)
        monitor.record(0.5, {"AMT_CREDIT": 1000.0})
        assert monitor.buffer_count == 1


class TestCompute:
    def test_min_samples_no_compute(self, tmp_path: Path):
        monitor = _make_monitor(tmp_path, min_samples=50)
        _fill_buffer(monitor, 10)
        result = monitor.compute()
        assert result == {}

    def test_compute_writes_snapshot(self, tmp_path: Path):
        monitor = _make_monitor(tmp_path)
        runs_before = len(monitor._workspace.list_runs(monitor._project_id))
        _fill_buffer(monitor, 50)
        result = monitor.compute()
        assert result != {}
        runs_after = len(monitor._workspace.list_runs(monitor._project_id))
        assert runs_after == runs_before + 1

    def test_psi_identical_low(self, tmp_path: Path):
        ref = _make_reference_df(200)
        monitor = _make_monitor(tmp_path, reference_df=ref)
        for i in range(100):
            monitor.record(
                float(ref["score"].iloc[i]),
                {
                    "AMT_CREDIT": float(ref["AMT_CREDIT"].iloc[i]),
                    "DAYS_BIRTH": float(ref["DAYS_BIRTH"].iloc[i]),
                    "CODE_GENDER": str(ref["CODE_GENDER"].iloc[i]),
                },
            )
        result = monitor.compute()
        assert "score_psi" in result
        assert result["score_psi"] is not None
        assert result["score_psi"] < 0.25

    def test_psi_shifted_high(self, tmp_path: Path):
        ref = _make_reference_df(200)
        monitor = _make_monitor(tmp_path, reference_df=ref)
        _fill_buffer(monitor, 100, shift=0.5)
        result = monitor.compute()
        assert "score_psi" in result
        assert result["score_psi"] is not None
        assert result["score_psi"] > 0.1

    def test_compute_returns_drifted_count(self, tmp_path: Path):
        monitor = _make_monitor(tmp_path)
        _fill_buffer(monitor, 50, shift=0.5)
        result = monitor.compute()
        assert "drifted_count" in result
        assert "drifted_share" in result
        assert isinstance(result["drifted_count"], int)


class TestDriftFeatures:
    def test_drift_features_not_empty(self):
        assert len(DRIFT_FEATURES) > 0
        assert "CODE_GENDER" in DRIFT_FEATURES
        assert "AMT_CREDIT" in DRIFT_FEATURES
