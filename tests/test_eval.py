"""Tests for metrics and backtest."""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.eval.baselines import predict_naive, predict_heuristic, predict_simple_ml  # noqa: E402
from src.eval.metrics import compute_metrics  # noqa: E402
from src.eval.backtest import resolve_processed_version, run_backtest  # noqa: E402


def test_compute_metrics():
    y_true = [0.01, -0.02, 0.0, 0.03]
    y_pred = [0.01, 0.01, 0.0, 0.02]
    m = compute_metrics(y_true, y_pred)
    assert "mse" in m and "mae" in m and "rmse" in m and "r2" in m and "directional_accuracy" in m and "n_samples" in m
    assert m["n_samples"] == 4
    # Same sign: (0.01,0.01), (0,0), (0.03,0.02); different: (-0.02, 0.01) -> 3/4
    assert m["directional_accuracy"] == pytest.approx(0.75)
    assert m["mse"] >= 0


def test_compute_metrics_directional():
    y_true = np.array([0.01, -0.01, 0.02])
    y_pred = np.array([0.02, 0.01, -0.01])  # signs: (+,+), (-,+), (+,-) -> only first correct
    m = compute_metrics(y_true, y_pred)
    assert m["directional_accuracy"] == pytest.approx(1.0 / 3.0)


def test_naive_baseline():
    train = pd.DataFrame({"target_forward_return": [0.1, -0.1, 0.0]})
    test = pd.DataFrame({"target_forward_return": [0.01, -0.01]})
    pred = predict_naive(train, test, strategy="zero")
    np.testing.assert_array_almost_equal(pred, [0.0, 0.0])
    pred_mean = predict_naive(train, test, strategy="mean")
    np.testing.assert_array_almost_equal(pred_mean, [0.0, 0.0])


def test_heuristic_baseline():
    train = pd.DataFrame({"return_1d": [], "target_forward_return": []})
    test = pd.DataFrame({"return_1d": [0.01, -0.02], "target_forward_return": [0.0, 0.0]})
    pred = predict_heuristic(train, test)
    np.testing.assert_array_almost_equal(pred, [0.01, -0.02])


def test_simple_ml_baseline():
    train = pd.DataFrame({
        "return_1d": [0.01, -0.01, 0.02],
        "return_5d": [0.02, -0.02, 0.03],
        "target_forward_return": [0.01, -0.01, 0.02],
    })
    test = pd.DataFrame({
        "return_1d": [0.0, 0.01],
        "return_5d": [0.0, 0.01],
        "target_forward_return": [0.0, 0.0],
    })
    pred = predict_simple_ml(train, test)
    assert len(pred) == 2
    assert not np.any(np.isnan(pred))


def test_backtest_produces_summary_artifact():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        processed = tmp / "processed"
        reports = tmp / "reports"
        models = tmp / "models"
        reports.mkdir(parents=True)
        models.mkdir(parents=True)
        v = "v1"
        (processed / v).mkdir(parents=True)
        # Minimal features with split column
        rows = [
            "ticker,date,split,return_1d,return_5d,return_21d,volatility_5d,volatility_21d,range_hl,volume_pct_1d,target_forward_return",
            "AAPL,2024-01-22,train,0.01,0.02,0.03,0.01,0.01,0.01,0.0,0.01",
            "AAPL,2024-01-23,train,0.0,0.01,0.02,0.01,0.01,0.01,0.0,0.0",
            "AAPL,2024-01-27,test,-0.01,-0.01,0.0,0.01,0.01,0.01,0.0,-0.01",
            "AAPL,2024-01-28,test,0.01,0.0,0.01,0.01,0.01,0.01,0.0,0.01",
        ]
        (processed / v / "features.csv").write_text("\n".join(rows))

        config = {
            "paths": {"data_processed": str(processed), "reports": str(reports), "models": str(models)},
            "time_horizon": {"test_start": "2024-07-01"},
            "eval": {"processed_version": "v1"},
        }
        summary = run_backtest(config, processed_root=processed, dataset_version_hint="v1")

        assert "dataset_version" in summary and summary["dataset_version"] == "v1"
        assert "models" in summary
        assert "naive" in summary["models"]
        assert "heuristic" in summary["models"]
        assert "simple_ml" in summary["models"]
        assert summary["models"]["tensorflow"] is None
        for name in ["naive", "heuristic", "simple_ml"]:
            assert "mse" in summary["models"][name]
            assert "directional_accuracy" in summary["models"][name]
            assert summary["models"][name]["n_samples"] == 2

        out_file = reports / v / "metrics_summary.json"
        assert out_file.exists()
        with open(out_file) as f:
            loaded = json.load(f)
        assert loaded["models"]["naive"]["n_samples"] == 2


def test_walk_forward_and_report_deterministic():
    """Walk-forward backtest produces artifact and report; report is regenerated deterministically."""
    from src.eval.report import generate_report

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        processed = tmp / "processed"
        reports = tmp / "reports"
        models = tmp / "models"
        processed.mkdir()
        reports.mkdir()
        models.mkdir()
        v = "v1"
        (processed / v).mkdir()
        # Enough test rows for 2 windows (e.g. 2 days each, step 2)
        rows = [
            "ticker,date,split,return_1d,return_5d,return_21d,volatility_5d,volatility_21d,range_hl,volume_pct_1d,target_forward_return",
            "AAPL,2024-01-22,train,0.01,0.02,0.03,0.01,0.01,0.01,0.0,0.01",
            "AAPL,2024-01-23,train,0.0,0.01,0.02,0.01,0.01,0.01,0.0,0.0",
            "AAPL,2024-01-27,test,-0.01,-0.01,0.0,0.01,0.01,0.01,0.0,-0.01",
            "AAPL,2024-01-28,test,0.01,0.0,0.01,0.01,0.01,0.01,0.0,0.01",
            "AAPL,2024-01-29,test,0.0,0.01,0.0,0.01,0.01,0.01,0.0,0.0",
            "AAPL,2024-01-30,test,-0.01,0.0,-0.01,0.01,0.01,0.01,0.0,-0.005",
        ]
        (processed / v / "features.csv").write_text("\n".join(rows))
        (processed / v / "feature_manifest.json").write_text(json.dumps({"split_boundaries": {}}))

        config = {
            "paths": {"data_processed": str(processed), "reports": str(reports), "models": str(models)},
            "time_horizon": {"train_end": "2024-01-24", "val_start": "2024-01-25", "val_end": "2024-01-26", "test_start": "2024-01-27"},
            "tickers": {"symbols": ["AAPL"]},
            "eval": {"processed_version": "v1", "walk_forward": {"window_days": 2, "step_days": 2}},
        }
        run_backtest(config, processed_root=processed, dataset_version_hint="v1")

        artifact_path = reports / v / "backtest_run.json"
        report_path = reports / v / "backtest_report.md"
        assert artifact_path.exists()
        assert report_path.exists()
        report1 = report_path.read_text()
        assert "Backtest Report" in report1
        assert "Setup" in report1
        assert "Baseline" in report1
        assert "TensorFlow" in report1
        assert "Error analysis" in report1

        # Regenerate from stored artifact; must be identical
        report2 = generate_report(artifact_path, out_path=report_path)
        assert report2 == report_path.read_text()
        assert report1 == report2


def test_resolve_processed_version_latest():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "v1").mkdir()
        (tmp / "v1" / "features.csv").write_text("ticker,date,split,target_forward_return\n")
        (tmp / "v2").mkdir()
        (tmp / "v2" / "features.csv").write_text("ticker,date,split,target_forward_return\n")
        assert resolve_processed_version(tmp, "latest") == "v2"
        assert resolve_processed_version(tmp, "v1") == "v1"
