"""Tests for TensorFlow training pipeline and load/eval with shared metrics."""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("tensorflow")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.eval.metrics import compute_metrics  # noqa: E402
from src.train.data import load_train_val  # noqa: E402
from src.train.load import load_run_record, load_trained_model, predict_with_trained_model  # noqa: E402
from src.train.model import build_model  # noqa: E402
from src.train.train import run_training  # noqa: E402


def _make_processed_data(tmp_path: Path, version: str) -> None:
    """Create minimal processed features.csv with train/val splits."""
    (tmp_path / version).mkdir(parents=True)
    rows = [
        "ticker,date,split,return_1d,return_5d,return_21d,volatility_5d,volatility_21d,range_hl,volume_pct_1d,target_forward_return",
        "AAPL,2024-01-22,train,0.01,0.02,0.03,0.01,0.01,0.01,0.0,0.01",
        "AAPL,2024-01-23,train,0.0,0.01,0.02,0.01,0.01,0.01,0.0,0.0",
        "AAPL,2024-01-24,train,-0.01,0.0,0.01,0.01,0.01,0.01,0.0,-0.005",
        "AAPL,2024-01-25,val,0.02,0.01,0.02,0.01,0.01,0.01,0.0,0.015",
        "AAPL,2024-01-26,val,0.0,0.02,0.01,0.01,0.01,0.01,0.0,0.0",
    ]
    (tmp_path / version / "features.csv").write_text("\n".join(rows))
    manifest = {
        "raw_dataset_version": version,
        "split_boundaries": {"train_end": "2024-01-24", "val_start": "2024-01-25", "val_end": "2024-01-26", "test_start": "2024-01-27"},
    }
    (tmp_path / version / "feature_manifest.json").write_text(json.dumps(manifest, indent=2))


def test_build_model():
    model = build_model(n_features=7, units=16, dropout_rate=0.3, learning_rate=0.001)
    assert model.input_shape == (None, 7)
    assert model.output_shape == (None, 1)
    out = model.predict(np.zeros((2, 7), dtype=np.float32), verbose=0)
    assert out.shape == (2, 1)


def test_run_training_produces_artifact():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        processed = tmp / "processed"
        models = tmp / "models"
        processed.mkdir()
        models.mkdir()
        _make_processed_data(processed, "v1")

        config = {
            "paths": {"data_processed": str(processed), "models": str(models)},
            "time_horizon": {"train_end": "2024-01-24", "val_start": "2024-01-25", "val_end": "2024-01-26", "test_start": "2024-01-27"},
            "feature_windows": {},
            "training": {"epochs": 2, "batch_size": 2, "learning_rate": 0.001, "early_stopping_patience": 0},
            "train": {"processed_version": "v1"},
        }

        run_id = run_training(config, processed_root=processed, models_root=models, dataset_version_hint="v1")
        assert run_id.startswith("v1_")

        run_dir = models / run_id
        assert (run_dir / "model.keras").exists()
        assert (run_dir / "run_record.json").exists()
        assert (run_dir / "metrics_summary.json").exists()

        record = load_run_record(run_dir)
        assert record["run_id"] == run_id
        assert record["dataset_version"] == "v1"
        assert "config" in record
        assert record["config"]["training"]["epochs"] == 2
        assert "split_boundaries" in record
        assert "feature_manifest_path" in record
        assert "train_metrics" in record
        assert "val_metrics" in record
        assert "scaler" in record and "mean" in record["scaler"] and "scale" in record["scaler"]
        assert "feature_columns" in record
        assert "mse" in record["val_metrics"] and "directional_accuracy" in record["val_metrics"]
        # Self-describing artifact: reviewer can identify config, data, schema, metrics
        assert "config_hash" in record
        assert isinstance(record["config_hash"], str) and len(record["config_hash"]) == 64
        assert "git_commit_hash" in record  # may be None if not a git repo
        assert "random_seeds" in record
        assert record["random_seeds"].get("numpy") == record["random_seeds"].get("tensorflow") == 42
        assert "model_input_shape" in record
        assert record["model_input_shape"] == [None, len(record["feature_columns"])]

        summary = json.loads((run_dir / "metrics_summary.json").read_text())
        assert summary["run_id"] == run_id
        assert summary["config_hash"] == record["config_hash"]
        assert summary["dataset_version"] == "v1"
        assert summary["feature_columns"] == record["feature_columns"]
        assert "train_metrics" in summary and "val_metrics" in summary


def test_loaded_model_evaluates_with_same_metrics():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        processed = tmp / "processed"
        models = tmp / "models"
        processed.mkdir()
        models.mkdir()
        _make_processed_data(processed, "v1")

        config = {
            "paths": {"data_processed": str(processed), "models": str(models)},
            "training": {"epochs": 2, "batch_size": 2, "early_stopping_patience": 0},
            "train": {"processed_version": "v1"},
        }
        run_id = run_training(config, processed_root=processed, models_root=models, dataset_version_hint="v1")
        run_dir = models / run_id

        model, record = load_trained_model(run_dir)
        train_df, val_df = load_train_val(processed, "v1")
        y_val_true = val_df["target_forward_return"].astype(float).values
        y_val_pred = predict_with_trained_model(model, record, val_df)
        metrics = compute_metrics(y_val_true, y_val_pred)
        assert "mse" in metrics and "directional_accuracy" in metrics
        assert metrics["n_samples"] == len(val_df)
        assert not np.any(np.isnan(y_val_pred))
