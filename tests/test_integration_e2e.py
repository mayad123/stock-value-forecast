"""
Integration test: small end-to-end pipeline on a tiny ticker set and short date range.
Runs build-features -> train -> backtest; asserts leakage constraints are satisfied (no LeakageError/TimeOrderingError)
and artifacts exist. Fails CI if leakage is violated.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _make_minimal_raw(raw_root: Path, version: str = "v1") -> None:
    """One ticker, ~30 days of prices so we get a few feature rows (lookback 21)."""
    norm_dir = raw_root / "prices_normalized" / version
    norm_dir.mkdir(parents=True)
    rows = ["ticker,date,open,high,low,close,adjusted_close,volume"]
    for i in range(30):
        d = f"2024-01-{i+1:02d}"
        p = 100.0 + i * 0.5
        v = 1_000_000 + i * 1000
        rows.append(f"AAPL,{d},{p},{p+1},{p-1},{p},{p},{v}")
    (norm_dir / "prices.csv").write_text("\n".join(rows))
    (raw_root / "manifests").mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset_version": version,
        "tickers": ["AAPL"],
        "normalized_paths": [f"prices_normalized/{version}/prices.csv"],
    }
    (raw_root / "manifests" / f"{version}.json").write_text(json.dumps(manifest, indent=2))


# Short date range and strict boundaries so no gap
E2E_CONFIG = {
    "paths": {"data_raw": "", "data_processed": "", "models": "", "reports": ""},
    "tickers": {"symbols": ["AAPL"]},
    "feature_windows": {"lookback_days": 21, "forward_return_days": 1},
    "time_horizon": {
        "train_end": "2024-01-24",
        "val_start": "2024-01-25",
        "val_end": "2024-01-26",
        "test_start": "2024-01-27",
    },
    "feature_build": {"raw_dataset_version": "v1"},
    "train": {"processed_version": "v1"},
    "eval": {"processed_version": "v1"},
    "training": {"epochs": 2, "batch_size": 2, "learning_rate": 0.001, "early_stopping_patience": 0},
}


def test_e2e_build_features_produces_valid_artifacts_no_leakage():
    """
    Run build-features on minimal raw data. Completing without LeakageError/TimeOrderingError
    proves leakage and ordering constraints are satisfied.
    """
    from src.features.price_features import run_build_features
    from src.features.split import LeakageError, TimeOrderingError

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        raw_root = tmp / "raw"
        processed_root = tmp / "processed"
        raw_root.mkdir()
        processed_root.mkdir()
        _make_minimal_raw(raw_root)

        config = {**E2E_CONFIG}
        config["paths"] = {"data_raw": str(raw_root), "data_processed": str(processed_root)}

        try:
            run_build_features(config, raw_root=raw_root, processed_root=processed_root)
        except (LeakageError, TimeOrderingError) as e:
            pytest.fail(f"Pipeline must not violate leakage or time ordering: {e}")

        features_csv = processed_root / "v1" / "features.csv"
        assert features_csv.exists(), "features.csv must be produced"
        manifest_path = processed_root / "v1" / "feature_manifest.json"
        assert manifest_path.exists()
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert "split_boundaries" in manifest
        assert "leakage_rule" in manifest
        assert manifest["split_boundaries"]["train_end"] == "2024-01-24"
        assert manifest["split_boundaries"]["test_start"] == "2024-01-27"
        assert "split_counts" in manifest
        assert manifest["split_counts"]["train"] >= 1
        assert "feature_columns" in manifest


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("tensorflow") is None,
    reason="tensorflow not installed",
)
def test_e2e_build_features_then_train_no_leakage():
    """
    Run build-features then train on minimal data. No LeakageError/TimeOrderingError.
    """
    from src.features.price_features import run_build_features
    from src.features.split import LeakageError, TimeOrderingError
    from src.train.train import run_training

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        raw_root = tmp / "raw"
        processed_root = tmp / "processed"
        models_root = tmp / "models"
        raw_root.mkdir()
        processed_root.mkdir()
        models_root.mkdir()
        _make_minimal_raw(raw_root)

        config = {**E2E_CONFIG}
        config["paths"] = {
            "data_raw": str(raw_root),
            "data_processed": str(processed_root),
            "models": str(models_root),
        }

        try:
            run_build_features(config, raw_root=raw_root, processed_root=processed_root)
        except (LeakageError, TimeOrderingError) as e:
            pytest.fail(f"Build-features must not violate constraints: {e}")

        try:
            run_id = run_training(
                config,
                processed_root=processed_root,
                models_root=models_root,
                dataset_version_hint="v1",
            )
        except (LeakageError, TimeOrderingError) as e:
            pytest.fail(f"Train must not violate constraints: {e}")

        assert run_id
        run_dir = models_root / run_id
        assert (run_dir / "model.keras").exists()
        assert (run_dir / "run_record.json").exists()
        with open(run_dir / "run_record.json") as f:
            record = json.load(f)
        assert record["dataset_version"] == "v1"
        assert "feature_columns" in record
        assert "split_boundaries" in record


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("tensorflow") is None,
    reason="tensorflow not installed",
)
def test_e2e_full_pipeline_build_train_backtest():
    """
    Full chain: build-features -> train -> backtest on minimal data. Asserts no leakage and artifacts exist.
    """
    from src.eval.backtest import run_backtest
    from src.features.price_features import run_build_features
    from src.features.split import LeakageError, TimeOrderingError
    from src.train.train import run_training

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        raw_root = tmp / "raw"
        processed_root = tmp / "processed"
        models_root = tmp / "models"
        reports_root = tmp / "reports"
        raw_root.mkdir()
        processed_root.mkdir()
        models_root.mkdir()
        reports_root.mkdir()
        _make_minimal_raw(raw_root)

        config = {**E2E_CONFIG}
        config["paths"] = {
            "data_raw": str(raw_root),
            "data_processed": str(processed_root),
            "models": str(models_root),
            "reports": str(reports_root),
        }

        try:
            run_build_features(config, raw_root=raw_root, processed_root=processed_root)
            run_id = run_training(
                config,
                processed_root=processed_root,
                models_root=models_root,
                dataset_version_hint="v1",
            )
            # run_backtest reads models path from config["paths"]["models"]
            summary = run_backtest(
                config,
                processed_root=processed_root,
                dataset_version_hint="v1",
            )
        except (LeakageError, TimeOrderingError) as e:
            pytest.fail(f"E2E pipeline must not violate leakage or time ordering: {e}")

        assert run_id
        assert isinstance(summary, dict)
        assert "dataset_version" in summary or "models" in summary
        assert (models_root / run_id / "model.keras").exists()
        assert (processed_root / "v1" / "features.csv").exists()
