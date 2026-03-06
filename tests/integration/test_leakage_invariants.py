"""
Enforced invariants: time ordering and leakage checks.
These tests intentionally trigger TimeOrderingError or LeakageError. They fail reliably
if the corresponding checks are removed or bypassed in src/features/split.py (or sentiment).
"""

import pandas as pd
import pytest

from src.features.split import (
    LeakageError,
    TimeOrderingError,
    apply_split,
    get_split_boundaries,
    validate_boundaries,
    validate_prediction_cutoff_per_ticker,
    validate_time_ordering_processed,
    validate_time_ordering_raw,
)


# --- TimeOrderingError: split boundaries and ordering ---


def test_invariant_time_ordering_missing_split_boundaries():
    """TimeOrderingError when time_horizon is missing required keys."""
    with pytest.raises(TimeOrderingError, match="time_horizon must define|Missing"):
        get_split_boundaries({})
    with pytest.raises(TimeOrderingError):
        get_split_boundaries({"time_horizon": {"train_end": "2023-12-31"}})


def test_invariant_time_ordering_train_end_after_val_start():
    """TimeOrderingError when train_end >= val_start."""
    with pytest.raises(TimeOrderingError, match="train_end.*val_start"):
        validate_boundaries({
            "train_end": "2024-01-15",
            "val_start": "2024-01-01",
            "val_end": "2024-06-30",
            "test_start": "2024-07-01",
        })


def test_invariant_time_ordering_val_start_after_val_end():
    """TimeOrderingError when val_start > val_end."""
    with pytest.raises(TimeOrderingError, match="val_start.*val_end"):
        validate_boundaries({
            "train_end": "2023-12-31",
            "val_start": "2024-06-30",
            "val_end": "2024-01-01",
            "test_start": "2024-07-01",
        })


def test_invariant_time_ordering_val_end_after_test_start():
    """TimeOrderingError when val_end >= test_start."""
    with pytest.raises(TimeOrderingError, match="val_end.*test_start"):
        validate_boundaries({
            "train_end": "2023-12-31",
            "val_start": "2024-01-01",
            "val_end": "2024-07-01",
            "test_start": "2024-07-01",
        })


def test_invariant_time_ordering_gap_dates_in_apply_split():
    """TimeOrderingError when data has dates in gap between val_end and test_start."""
    b = {
        "train_end": "2023-12-31",
        "val_start": "2024-01-01",
        "val_end": "2024-06-29",
        "test_start": "2024-07-01",
    }
    df = pd.DataFrame([{"ticker": "A", "date": "2024-06-30", "x": 1}])
    with pytest.raises(TimeOrderingError, match="gap"):
        apply_split(df, b)


def test_invariant_time_ordering_raw_duplicate_ticker_date():
    """TimeOrderingError when raw data has duplicate (ticker, date)."""
    df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-01"},
        {"ticker": "A", "date": "2024-01-01"},
    ])
    with pytest.raises(TimeOrderingError, match="duplicate"):
        validate_time_ordering_raw(df)


def test_invariant_time_ordering_processed_duplicate():
    """TimeOrderingError when processed data has duplicate (ticker, date)."""
    df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-01"},
        {"ticker": "A", "date": "2024-01-01"},
    ])
    with pytest.raises(TimeOrderingError, match="duplicate"):
        validate_time_ordering_processed(df)


def test_invariant_time_ordering_processed_unsorted():
    """TimeOrderingError when processed data is not sorted by (ticker, date)."""
    df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-03"},
        {"ticker": "A", "date": "2024-01-01"},
        {"ticker": "A", "date": "2024-01-02"},
    ])
    with pytest.raises(TimeOrderingError, match="not sorted"):
        validate_time_ordering_processed(df)


# --- LeakageError: future-dated inputs relative to cutoff ---


def test_invariant_leakage_raw_unsorted():
    """LeakageError when raw data is not sorted by (ticker, date) (risks future leak)."""
    df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-03"},
        {"ticker": "A", "date": "2024-01-01"},
        {"ticker": "A", "date": "2024-01-02"},
    ])
    with pytest.raises(LeakageError, match="not sorted|chronological"):
        validate_time_ordering_raw(df)


def test_invariant_leakage_raw_missing_columns():
    """LeakageError when raw data lacks ticker/date columns for ordering checks."""
    df = pd.DataFrame([{"x": 1}])
    with pytest.raises(LeakageError, match="ticker|date"):
        validate_time_ordering_raw(df)


def test_invariant_leakage_processed_date_after_raw_max():
    """LeakageError when processed row has date after latest raw date for that ticker."""
    raw_df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-01"},
        {"ticker": "A", "date": "2024-01-02"},
    ])
    processed_df = pd.DataFrame([
        {"ticker": "A", "date": "2024-01-03"},
    ])
    with pytest.raises(LeakageError, match="after latest raw date|prediction cutoff"):
        validate_prediction_cutoff_per_ticker(raw_df, processed_df)


def test_invariant_leakage_ticker_missing_in_raw():
    """LeakageError when processed has ticker with no observations in raw."""
    raw_df = pd.DataFrame([{"ticker": "A", "date": "2024-01-01"}])
    processed_df = pd.DataFrame([{"ticker": "B", "date": "2024-01-01"}])
    with pytest.raises(LeakageError, match="no observations for that ticker"):
        validate_prediction_cutoff_per_ticker(raw_df, processed_df)
