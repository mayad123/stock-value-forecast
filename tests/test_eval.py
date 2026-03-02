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

        # Every run writes latest_* (overwritten each run)
        latest_json = reports / "latest_metrics.json"
        latest_md = reports / "latest_backtest.md"
        assert latest_json.exists()
        assert latest_md.exists()
        with open(latest_json) as f:
            latest = json.load(f)
        assert isinstance(latest, dict)
        assert "dataset_version" in latest and "models" in latest
        assert latest["models"]["naive"]["n_samples"] == 2
        assert "Dataset version" in latest_md.read_text()
        assert "Split boundaries" in latest_md.read_text()
        assert "Notes" in latest_md.read_text()
        # Single-window also writes predictions CSV (fold_id = -1)
        latest_pred = reports / "latest_predictions.csv"
        assert latest_pred.exists()
        pred_df = pd.read_csv(latest_pred)
        assert "y_true" in pred_df.columns and "y_pred" in pred_df.columns and "model_name" in pred_df.columns
        assert (reports / v / "predictions.csv").exists()


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

        # Every run writes latest_* (overwritten each run)
        latest_json = reports / "latest_metrics.json"
        latest_md = reports / "latest_backtest.md"
        assert latest_json.exists()
        assert latest_md.exists()
        with open(latest_json) as f:
            latest = json.load(f)
        assert isinstance(latest, dict)
        assert "dataset_version" in latest and "models" in latest
        assert "Notes" in latest_md.read_text()


def test_backtest_overwrites_latest_preserves_versioned():
    """Running backtest twice overwrites latest_*.json/.md; versioned outputs (reports/<version>/) remain."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        processed = tmp / "processed"
        reports = tmp / "reports"
        models = tmp / "models"
        reports.mkdir(parents=True)
        models.mkdir(parents=True)
        v = "v1"
        (processed / v).mkdir(parents=True)
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
            "eval": {},
        }
        run_backtest(config, processed_root=processed, dataset_version_hint="v1")
        latest_json = reports / "latest_metrics.json"
        latest_md = reports / "latest_backtest.md"
        first_json = json.loads(latest_json.read_text())
        run_backtest(config, processed_root=processed, dataset_version_hint="v1")
        second_json = json.loads(latest_json.read_text())
        second_md = latest_md.read_text()
        assert first_json["dataset_version"] == second_json["dataset_version"] == "v1"
        assert "models" in second_json
        assert (reports / v / "metrics_summary.json").exists()
        assert (reports / v / "backtest_report.md").exists()
        assert "Notes" in second_md


def test_backtest_walk_forward_produces_at_least_two_folds_and_latest_has_folds_aggregate():
    """Backtest on sample data with eval fold/step produces >= 2 folds; latest_metrics.json has folds and aggregate."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        processed = tmp / "processed"
        reports = tmp / "reports"
        models = tmp / "models"
        reports.mkdir(parents=True)
        models.mkdir(parents=True)
        v = "demo"
        (processed / v).mkdir(parents=True)
        rows = [
            "ticker,date,split,return_1d,return_5d,return_21d,volatility_5d,volatility_21d,range_hl,volume_pct_1d,target_forward_return",
            "AAPL,2024-01-11,train,0.01,0.02,0.03,0.01,0.01,0.01,0.0,0.01",
            "AAPL,2024-01-12,train,0.0,0.01,0.02,0.01,0.01,0.01,0.0,0.0",
        ]
        # Enough train dates and test dates for 2+ folds (fold_size=5, step=5)
        for i in range(12):
            rows.append(f"AAPL,2024-01-{13+i:02d},train,0.0,0.01,0.02,0.01,0.01,0.01,0.0,0.0")
        for i in range(15):
            rows.append(f"AAPL,2024-02-{1+i:02d},test,0.0,0.01,0.0,0.01,0.01,0.01,0.0,0.001")
        (processed / v / "features.csv").write_text("\n".join(rows))
        config = {
            "paths": {"data_processed": str(processed), "reports": str(reports), "models": str(models)},
            "time_horizon": {"train_end": "2024-01-24", "val_start": "2024-01-25", "val_end": "2024-01-26", "test_start": "2024-02-01"},
            "eval": {"min_train_days": 5, "fold_size_days": 5, "step_size_days": 5},
        }
        result = run_backtest(config, processed_root=processed, dataset_version_hint=v)
        assert "folds" in result
        assert len(result["folds"]) >= 2
        assert "aggregate" in result
        assert "naive" in result["aggregate"]
        latest_json = reports / "latest_metrics.json"
        assert latest_json.exists()
        latest = json.loads(latest_json.read_text())
        assert "folds" in latest
        assert "aggregate" in latest
        assert len(latest["folds"]) >= 2
        # Predictions CSV for plotting: time-aligned y_true, y_pred, model_name, fold_id
        latest_pred = reports / "latest_predictions.csv"
        assert latest_pred.exists(), "backtest must write reports/latest_predictions.csv"
        pred_df = pd.read_csv(latest_pred)
        for col in ["ticker", "asof_date", "target_date", "y_true", "y_pred", "model_name", "fold_id"]:
            assert col in pred_df.columns, f"predictions CSV must have column {col}"
        assert len(pred_df["fold_id"].unique()) >= 2, "demo mode must produce predictions for >= 2 folds"
        assert set(pred_df["model_name"].unique()) & {"naive", "heuristic", "simple_ml"}, "must include baselines"
        versioned_pred = reports / v / "predictions.csv"
        assert versioned_pred.exists(), "backtest must write reports/<version>/predictions.csv"


def test_resolve_processed_version_latest():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "v1").mkdir()
        (tmp / "v1" / "features.csv").write_text("ticker,date,split,target_forward_return\n")
        (tmp / "v2").mkdir()
        (tmp / "v2" / "features.csv").write_text("ticker,date,split,target_forward_return\n")
        assert resolve_processed_version(tmp, "latest") == "v2"
        assert resolve_processed_version(tmp, "v1") == "v1"
