"""Tests for deterministic feature generation."""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.features.price_features import (  # noqa: E402
    FEATURE_NAMES,
    TARGET_NAME,
    build_features,
    load_raw_normalized,
    resolve_raw_version,
    run_build_features,
)
from src.features.split import (  # noqa: E402
    TimeOrderingError,
    get_split_boundaries,
    validate_boundaries,
    validate_time_ordering_raw,
)


def _make_raw_normalized(tmp_path: Path, version: str) -> None:
    """Create minimal raw normalized CSV and manifest for testing."""
    norm_dir = tmp_path / "prices_normalized" / version
    norm_dir.mkdir(parents=True)
    csv = norm_dir / "prices.csv"
    # Minimal OHLCV: 30 days for one ticker so we get some feature rows (need lookback 21)
    rows = [
        "ticker,date,open,high,low,close,adjusted_close,volume",
    ]
    for i in range(30):
        d = f"2024-01-{i+1:02d}"
        price = 100.0 + i * 0.5
        vol = 1_000_000 + i * 1000
        rows.append(f"AAPL,{d},{price},{price+1},{price-1},{price},{price},{vol}")
    csv.write_text("\n".join(rows))

    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir(parents=True)
    manifest = {
        "dataset_version": version,
        "tickers": ["AAPL"],
        "normalized_paths": [f"prices_normalized/{version}/prices.csv"],
    }
    (manifest_dir / f"{version}.json").write_text(json.dumps(manifest, indent=2))


def test_build_features_deterministic():
    """Running build_features twice on same input yields identical output."""
    import pandas as pd

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _make_raw_normalized(tmp, "v1")
        df = load_raw_normalized(tmp, "v1")
        out1 = build_features(df, lookback_days=21, forward_return_days=1)
        out2 = build_features(df, lookback_days=21, forward_return_days=1)

        assert out1.shape == out2.shape
        assert list(out1.columns) == list(out2.columns)
        pd.testing.assert_frame_equal(out1, out2)


def test_run_build_features_twice_same_output():
    """Running run_build_features twice on same raw dataset yields identical processed files."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        raw_root = tmp / "raw"
        raw_root.mkdir()
        processed_root = tmp / "processed"
        _make_raw_normalized(raw_root, "v1")

        config = {
            "paths": {"data_raw": str(raw_root), "data_processed": str(processed_root)},
            "feature_windows": {"lookback_days": 21, "forward_return_days": 1},
            "time_horizon": {
                "train_end": "2024-01-24",
                "val_start": "2024-01-25",
                "val_end": "2024-01-26",
                "test_start": "2024-01-27",
            },
            "feature_build": {"raw_dataset_version": "v1"},
        }

        run_build_features(config, raw_root=raw_root, processed_root=processed_root)
        features_path = processed_root / "v1" / "features.csv"
        assert features_path.exists()
        content1 = features_path.read_text()
        hash1 = hashlib.sha256(content1.encode()).hexdigest()

        run_build_features(config, raw_root=raw_root, processed_root=processed_root)
        content2 = features_path.read_text()
        hash2 = hashlib.sha256(content2.encode()).hexdigest()

        assert hash1 == hash2, "Second run must produce identical features.csv"
        assert (processed_root / "v1" / "feature_manifest.json").exists()


def test_resolve_raw_version_latest():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "manifests").mkdir()
        (tmp / "manifests" / "2024-01-01T00-00-00.json").write_text("{}")
        (tmp / "manifests" / "2024-01-02T00-00-00.json").write_text("{}")
        v = resolve_raw_version(tmp, "latest")
        assert v == "2024-01-02T00-00-00"


def test_feature_manifest_links_raw():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        raw_root = tmp / "raw"
        raw_root.mkdir()
        processed_root = tmp / "processed"
        _make_raw_normalized(raw_root, "v1")
        config = {
            "paths": {"data_raw": str(raw_root), "data_processed": str(processed_root)},
            "feature_windows": {"lookback_days": 21, "forward_return_days": 1},
            "time_horizon": {
                "train_end": "2024-01-24",
                "val_start": "2024-01-25",
                "val_end": "2024-01-26",
                "test_start": "2024-01-27",
            },
            "feature_build": {"raw_dataset_version": "v1"},
        }
        run_build_features(config, raw_root=raw_root, processed_root=processed_root)

        with open(processed_root / "v1" / "feature_manifest.json") as f:
            manifest = json.load(f)
        assert manifest["raw_dataset_version"] == "v1"
        assert "feature_definitions" in manifest
        assert "feature_windows" in manifest
        assert "split_boundaries" in manifest
        assert manifest["split_boundaries"]["train_end"] == "2024-01-24"
        assert "split_counts" in manifest
        assert manifest["feature_columns"] == FEATURE_NAMES
        assert manifest["target_column"] == TARGET_NAME


def test_split_boundaries_must_be_ordered():
    """Pipeline fails loudly if split boundaries violate time ordering."""
    with pytest.raises(TimeOrderingError, match="train_end.*val_start"):
        validate_boundaries({
            "train_end": "2024-01-31",
            "val_start": "2024-01-01",
            "val_end": "2024-06-30",
            "test_start": "2024-07-01",
        })
    with pytest.raises(TimeOrderingError, match="val_end.*test_start"):
        validate_boundaries({
            "train_end": "2023-12-31",
            "val_start": "2024-01-01",
            "val_end": "2024-07-01",
            "test_start": "2024-07-01",
        })


def test_missing_split_boundaries_fails():
    """Pipeline fails if time_horizon is missing required boundaries."""
    with pytest.raises(TimeOrderingError, match="time_horizon must define"):
        get_split_boundaries({"time_horizon": {}})


def test_raw_duplicate_ticker_date_fails():
    """Pipeline fails if raw data has duplicate (ticker, date)."""
    import pandas as pd
    df = pd.DataFrame([
        {"ticker": "AAPL", "date": "2024-01-01", "close": 100},
        {"ticker": "AAPL", "date": "2024-01-01", "close": 101},
    ])
    with pytest.raises(TimeOrderingError, match="duplicate"):
        validate_time_ordering_raw(df)
