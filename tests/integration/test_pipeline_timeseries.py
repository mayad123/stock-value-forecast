"""
Time-series correctness: split boundaries, leakage detection, and ordering.
All tests must pass in CI; leakage constraints failing here must fail the build.
"""

from pathlib import Path

import pandas as pd
import pytest

from src.features.split import (
    LeakageError,
    TimeOrderingError,
    assign_split,
    apply_split,
    get_split_boundaries,
    validate_boundaries,
    validate_prediction_cutoff_per_ticker,
    validate_time_ordering_processed,
    validate_time_ordering_raw,
)


# --- Split boundaries correctness ---

def test_get_split_boundaries_returns_all_keys():
    config = {
        "time_horizon": {
            "train_end": "2023-12-31",
            "val_start": "2024-01-01",
            "val_end": "2024-06-30",
            "test_start": "2024-07-01",
        }
    }
    b = get_split_boundaries(config)
    assert b["train_end"] == "2023-12-31"
    assert b["val_start"] == "2024-01-01"
    assert b["val_end"] == "2024-06-30"
    assert b["test_start"] == "2024-07-01"


def test_get_split_boundaries_missing_key_raises():
    with pytest.raises(TimeOrderingError, match="time_horizon must define|Missing"):
        get_split_boundaries({})
    with pytest.raises(TimeOrderingError):
        get_split_boundaries({"time_horizon": {"train_end": "2023-12-31"}})


def test_validate_boundaries_accepts_valid_ordering():
    validate_boundaries({
        "train_end": "2023-12-31",
        "val_start": "2024-01-01",
        "val_end": "2024-06-30",
        "test_start": "2024-07-01",
    })


def test_validate_boundaries_rejects_train_after_val_start():
    with pytest.raises(TimeOrderingError, match="train_end.*val_start"):
        validate_boundaries({
            "train_end": "2024-01-15",
            "val_start": "2024-01-01",
            "val_end": "2024-06-30",
            "test_start": "2024-07-01",
        })


def test_validate_boundaries_rejects_val_end_after_test_start():
    with pytest.raises(TimeOrderingError, match="val_end.*test_start"):
        validate_boundaries({
            "train_end": "2023-12-31",
            "val_start": "2024-01-01",
            "val_end": "2024-07-01",
            "test_start": "2024-07-01",
        })


def test_assign_split_train_val_test_at_boundaries():
    b = {
        "train_end": "2023-12-31",
        "val_start": "2024-01-01",
        "val_end": "2024-06-30",
        "test_start": "2024-07-01",
    }
    assert assign_split("2023-12-30", b) == "train"
    assert assign_split("2023-12-31", b) == "train"
    assert assign_split("2024-01-01", b) == "val"
    assert assign_split("2024-06-30", b) == "val"
    assert assign_split("2024-07-01", b) == "test"
    assert assign_split("2024-08-01", b) == "test"


def test_assign_split_returns_gap_between_val_end_and_test_start():
    b = {
        "train_end": "2023-12-31",
        "val_start": "2024-01-01",
        "val_end": "2024-06-30",
        "test_start": "2024-07-01",
    }
    assert assign_split("2024-06-30", b) == "val"
    assert assign_split("2024-07-01", b) == "test"
    # Any date strictly between val_end and test_start is gap (if such exists with day granularity)
    # Here val_end=06-30, test_start=07-01 so there is no gap day; if we had val_end=06-29, test_start=07-01:
    b2 = {"train_end": "2023-12-31", "val_start": "2024-01-01", "val_end": "2024-06-29", "test_start": "2024-07-01"}
    assert assign_split("2024-06-30", b2) == "gap"


def test_apply_split_raises_on_gap_dates():
    b = {
        "train_end": "2023-12-31",
        "val_start": "2024-01-01",
        "val_end": "2024-06-29",
        "test_start": "2024-07-01",
    }
    df = pd.DataFrame([
        {"ticker": "A", "date": "2024-06-30", "x": 1},
    ])
    with pytest.raises(TimeOrderingError, match="gap"):
        apply_split(df, b)


def test_apply_split_counts_match_boundaries():
    b = {
        "train_end": "2024-01-24",
        "val_start": "2024-01-25",
        "val_end": "2024-01-26",
        "test_start": "2024-01-27",
    }
    df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-22"},
        {"ticker": "A", "date": "2024-01-23"},
        {"ticker": "A", "date": "2024-01-24"},
        {"ticker": "A", "date": "2024-01-25"},
        {"ticker": "A", "date": "2024-01-26"},
        {"ticker": "A", "date": "2024-01-27"},
    ])
    out, counts = apply_split(df, b)
    assert counts["train"] == 3
    assert counts["val"] == 2
    assert counts["test"] == 1
    assert list(out["split"]) == ["train", "train", "train", "val", "val", "test"]


# --- Leakage detection rules ---

def test_validate_time_ordering_raw_raises_on_unsorted():
    """Unsorted raw data risks leakage; must raise LeakageError."""
    df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-03"},
        {"ticker": "A", "date": "2024-01-01"},
        {"ticker": "A", "date": "2024-01-02"},
    ])
    with pytest.raises(LeakageError, match="not sorted|chronological"):
        validate_time_ordering_raw(df)


def test_validate_time_ordering_raw_raises_on_duplicate_ticker_date():
    df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-01"},
        {"ticker": "A", "date": "2024-01-01"},
    ])
    with pytest.raises(TimeOrderingError, match="duplicate"):
        validate_time_ordering_raw(df)


def test_validate_time_ordering_raw_passes_sorted_no_dupes():
    df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-01"},
        {"ticker": "A", "date": "2024-01-02"},
    ])
    validate_time_ordering_raw(df)


def test_validate_time_ordering_processed_raises_on_duplicate():
    df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-01", "x": 1},
        {"ticker": "A", "date": "2024-01-01", "x": 2},
    ])
    with pytest.raises(TimeOrderingError, match="duplicate"):
        validate_time_ordering_processed(df)


def test_validate_prediction_cutoff_raises_when_processed_date_after_raw_max():
    """Processed row must not have date after latest raw date for that ticker (leakage)."""
    raw_df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-10"},
        {"ticker": "A", "date": "2024-01-11"},
    ])
    processed_df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-11"},
        {"ticker": "A", "date": "2024-01-15"},  # after max raw 2024-01-11
    ])
    with pytest.raises(LeakageError, match="after latest raw date|prediction cutoff"):
        validate_prediction_cutoff_per_ticker(raw_df, processed_df)


def test_validate_prediction_cutoff_raises_when_ticker_missing_in_raw():
    raw_df = pd.DataFrame([{"ticker": "A", "date": "2024-01-10"}])
    processed_df = pd.DataFrame([{"ticker": "B", "date": "2024-01-10"}])
    with pytest.raises(LeakageError, match="no observations for that ticker"):
        validate_prediction_cutoff_per_ticker(raw_df, processed_df)


def test_validate_prediction_cutoff_passes_when_processed_dates_within_raw():
    raw_df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-10"},
        {"ticker": "A", "date": "2024-01-11"},
        {"ticker": "A", "date": "2024-01-12"},
    ])
    processed_df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-11"},
        {"ticker": "A", "date": "2024-01-12"},
    ])
    validate_prediction_cutoff_per_ticker(raw_df, processed_df)


def test_validate_prediction_cutoff_empty_dfs_pass():
    validate_prediction_cutoff_per_ticker(pd.DataFrame(), pd.DataFrame())
    validate_prediction_cutoff_per_ticker(
        pd.DataFrame([{"ticker": "A", "date": "2024-01-01"}]),
        pd.DataFrame(),
    )


# --- Feature generation determinism (time-series safe) ---

def test_feature_generation_deterministic_same_input_same_output():
    """Same raw input and config must produce identical feature rows (reproducibility)."""
    from datetime import datetime, timedelta
    from src.features.price_features import build_features, load_raw_normalized

    with __import__("tempfile").TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "prices_normalized" / "v1").mkdir(parents=True)
        (tmp / "manifests").mkdir(parents=True)
        rows = ["ticker,date,open,high,low,close,adjusted_close,volume"]
        start = datetime(2024, 1, 1)
        for i in range(35):
            d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            p = 100.0 + i * 0.5
            v = 1_000_000
            rows.append(f"AAPL,{d},{p},{p+1},{p-1},{p},{p},{v}")
        (tmp / "prices_normalized" / "v1" / "prices.csv").write_text("\n".join(rows))
        (tmp / "manifests" / "v1.json").write_text('{"dataset_version":"v1","tickers":["AAPL"]}')

        df = load_raw_normalized(tmp, "v1")
        out1 = build_features(df, lookback_days=21, forward_return_days=1)
        out2 = build_features(df, lookback_days=21, forward_return_days=1)
        pd.testing.assert_frame_equal(out1, out2)
