"""Smoke tests for typed data contracts (src.types)."""

from src.types import (
    BacktestSummary,
    FeatureImportanceResult,
    FeatureManifest,
    ModelMetrics,
    RunRecord,
    ScalerDict,
)


def test_run_record_shape():
    """RunRecord documents run_record.json shape; can be used as type hint."""
    r: RunRecord = {
        "run_id": "v1_20240101T120000Z",
        "dataset_version": "v1",
        "feature_columns": ["a", "b"],
        "scaler": {"mean": [0.0], "scale": [1.0]},
    }
    assert r["run_id"] == "v1_20240101T120000Z"
    assert r["feature_columns"] == ["a", "b"]


def test_scaler_dict_shape():
    """ScalerDict documents scaler stored in run record."""
    s: ScalerDict = {"mean": [0.0, 0.0], "scale": [1.0, 1.0]}
    assert len(s["mean"]) == 2


def test_feature_manifest_shape():
    """FeatureManifest documents feature_manifest.json shape."""
    m: FeatureManifest = {
        "raw_dataset_version": "v1",
        "feature_columns": ["x", "y"],
        "split_boundaries": {"train_end": "2024-01-01"},
    }
    assert m["raw_dataset_version"] == "v1"


def test_model_metrics_shape():
    """ModelMetrics documents metrics dict from compute_metrics."""
    metrics: ModelMetrics = {"mse": 0.1, "mae": 0.2, "n_samples": 100}
    assert metrics["mse"] == 0.1
    assert metrics["n_samples"] == 100


def test_backtest_summary_shape():
    """BacktestSummary documents single-window backtest result."""
    b: BacktestSummary = {"dataset_version": "v1", "models": {"naive": {"mse": 0.01}}, "n_test": 50}
    assert "naive" in b["models"]
    assert b["n_test"] == 50


def test_feature_importance_result_shape():
    """FeatureImportanceResult documents feature importance artifact and API response."""
    fi: FeatureImportanceResult = {
        "dataset_version": "v1",
        "model_run_id": "run1",
        "n_eval_samples": 100,
        "metric": "mse_increase",
        "n_repeats": 5,
        "feature_importance": [{"feature": "x", "importance": 0.1, "std": 0.01}],
    }
    assert len(fi["feature_importance"]) == 1
    assert fi["feature_importance"][0]["feature"] == "x"
