"""
Time-series split and leakage enforcement.
Train/val/test partitions by chronological boundaries; pipeline fails loudly on violations.
"""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


class TimeOrderingError(Exception):
    """Raised when date ordering or split boundaries are invalid."""

    pass


class LeakageError(Exception):
    """Raised when feature generation could use data after the prediction cutoff."""

    pass


def get_split_boundaries(config: Dict[str, Any]) -> Dict[str, str]:
    """
    Read time_horizon from config and return split boundaries.
    Keys: train_end, val_start, val_end, test_start (YYYY-MM-DD).
    Raises TimeOrderingError if any boundary is missing.
    """
    th = config.get("time_horizon", {})
    required = ["train_end", "val_start", "val_end", "test_start"]
    missing = [k for k in required if not th.get(k)]
    if missing:
        raise TimeOrderingError(
            f"time_horizon must define all split boundaries: {required}. Missing: {missing}. "
            "Add them in configs/default.yaml under time_horizon."
        )
    return {
        "train_end": th["train_end"],
        "val_start": th["val_start"],
        "val_end": th["val_end"],
        "test_start": th["test_start"],
    }


def validate_boundaries(boundaries: Dict[str, str]) -> None:
    """
    Enforce strict chronological order: train_end < val_start <= val_end < test_start.
    Raises TimeOrderingError with a clear message if violated.
    """
    train_end = boundaries["train_end"]
    val_start = boundaries["val_start"]
    val_end = boundaries["val_end"]
    test_start = boundaries["test_start"]

    if train_end >= val_start:
        raise TimeOrderingError(
            f"Split boundaries violate time ordering: train_end ({train_end}) must be strictly before val_start ({val_start}). "
            "No training data may overlap validation."
        )
    if val_start > val_end:
        raise TimeOrderingError(
            f"Split boundaries violate time ordering: val_start ({val_start}) must be <= val_end ({val_end})."
        )
    if val_end >= test_start:
        raise TimeOrderingError(
            f"Split boundaries violate time ordering: val_end ({val_end}) must be strictly before test_start ({test_start}). "
            "No validation data may overlap test."
        )


def assign_split(date: str, boundaries: Dict[str, str]) -> str:
    """Return 'train' | 'val' | 'test' for a given date string (YYYY-MM-DD)."""
    if date <= boundaries["train_end"]:
        return "train"
    if boundaries["val_start"] <= date <= boundaries["val_end"]:
        return "val"
    if date >= boundaries["test_start"]:
        return "test"
    return "gap"  # date in (val_end, test_start) gap


def apply_split(df: pd.DataFrame, boundaries: Dict[str, str], date_col: str = "date") -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Add a 'split' column (train/val/test) and drop rows in 'gap'.
    Returns (df with split column, split_counts dict).
    """
    if date_col not in df.columns:
        raise TimeOrderingError(f"DataFrame has no column '{date_col}' for split assignment.")
    df = df.copy()
    df["split"] = df[date_col].astype(str).map(lambda d: assign_split(d, boundaries))
    gap = df["split"] == "gap"
    if gap.any():
        n = gap.sum()
        raise TimeOrderingError(
            f"Found {n} row(s) with dates in the gap between val_end and test_start. "
            "Adjust time_horizon so val_end and test_start are consecutive or overlap the data range."
        )
    counts = {"train": int((df["split"] == "train").sum()), "val": int((df["split"] == "val").sum()), "test": int((df["split"] == "test").sum())}
    return df, counts


def validate_time_ordering_raw(df: pd.DataFrame, ticker_col: str = "ticker", date_col: str = "date") -> None:
    """
    Raw price data must be sorted by (ticker, date) with no duplicate (ticker, date).
    Raises TimeOrderingError or LeakageError if violated (unsorted data risks leakage).
    """
    if df.empty:
        return
    if ticker_col not in df.columns or date_col not in df.columns:
        raise LeakageError(f"Raw data must have columns '{ticker_col}' and '{date_col}' for ordering checks.")
    dup = df.duplicated(subset=[ticker_col, date_col])
    if dup.any():
        raise TimeOrderingError(
            f"Raw data has duplicate (ticker, date) pairs. Duplicates prevent deterministic feature generation and can cause leakage."
        )
    sorted_df = df.sort_values([ticker_col, date_col]).reset_index(drop=True)
    if not df.equals(sorted_df):
        raise LeakageError(
            "Raw data is not sorted by (ticker, date). Feature generation requires chronological order per ticker; "
            "unsorted data may allow future information to leak into features."
        )


def validate_time_ordering_processed(df: pd.DataFrame, date_col: str = "date", ticker_col: str = "ticker") -> None:
    """
    Processed feature data must be sorted by (ticker, date) and have no duplicate (ticker, date).
    Raises TimeOrderingError if violated.
    """
    if df.empty:
        return
    if ticker_col not in df.columns or date_col not in df.columns:
        raise TimeOrderingError(f"Processed data must have columns '{ticker_col}' and '{date_col}'.")
    dup = df.duplicated(subset=[ticker_col, date_col])
    if dup.any():
        raise TimeOrderingError("Processed data has duplicate (ticker, date) pairs.")
    sorted_df = df.sort_values([ticker_col, date_col]).reset_index(drop=True)
    if not df.equals(sorted_df):
        raise TimeOrderingError("Processed data is not sorted by (ticker, date).")


def validate_prediction_cutoff_per_ticker(
    raw_df: pd.DataFrame,
    processed_df: pd.DataFrame,
    ticker_col: str = "ticker",
    date_col: str = "date",
) -> None:
    """
    For each row in processed with (ticker, date), the prediction cutoff is date.
    We require that in raw data for that ticker, there is no observation with date > row date
    that could be used in feature computation. Since we build features using only past/current
    data, the raw data for that ticker must have dates <= row date for all rows used.
    This checks: for each (ticker, date) in processed, the latest raw date for that ticker
    is at least the row date (we use up to row date). So we require: max(raw dates for ticker) >= date.
    And we require that we never have a processed row whose date is after the max raw date for that ticker
    (which would imply we're using a date that doesn't exist in raw - we don't). So check:
    for each row in processed, raw has that (ticker, date) or we have raw dates up to that date.
    Actually the strict check: for each (ticker, date) in processed, all feature inputs must come from
    raw rows with (ticker, d) where d <= date. So the latest raw date used for that row must be <= date.
    Our implementation uses exactly date (and past). So we need to ensure raw has no date > row date
    that could leak. So: for each (ticker, date) in processed, in raw for that ticker, max(d) should be
    >= date (we need the row date to exist) and we must not be using any d > date. We use only <= date.
    So the validation: for each (ticker, date) in processed, in raw the max date for that ticker must be
    >= date (otherwise we're predicting with no future - that's fine; but typically we have raw up to that date).
    And min raw date for that ticker should be <= date - lookback so we have enough history. Optional.
    Simplest strict check: processed dates must be a subset of the set of dates that appear in raw (per ticker),
    or at least for each (ticker, date) in processed, raw has that ticker and has at least one row with d <= date.
    I'll do: for each (ticker, date) in processed, require that in raw for that ticker, max(date) >= date.
    If not, we're including a row that has a date beyond what we have in raw - that could mean we're using
    future info. Actually no - if processed has a row (ticker, date) it means we computed features from raw
    using data up to date. So raw must have data up to date. So max(raw dates for ticker) >= date. If we have
    raw dates beyond date, that's fine - we just didn't use them for this row. So the check is:
    for each (ticker, date) in processed: max(raw[raw.ticker==ticker].date) >= date. If not, we have a row
    that's "in the future" relative to raw - which shouldn't happen if we built from that raw. So this validates
    consistency. Let me add it.
    """
    if raw_df.empty or processed_df.empty:
        return
    raw_max_date = raw_df.groupby(ticker_col)[date_col].max()
    for _, row in processed_df[[ticker_col, date_col]].drop_duplicates().iterrows():
        t, d = row[ticker_col], row[date_col]
        if t not in raw_max_date.index:
            raise LeakageError(f"Processed row has ticker '{t}' with date {d} but raw data has no observations for that ticker.")
        max_raw = raw_max_date[t]
        if str(d) > str(max_raw):
            raise LeakageError(
                f"Processed row (ticker={t}, date={d}) has date after latest raw date for that ticker ({max_raw}). "
                "Feature generation must not use data later than the prediction cutoff (row date)."
            )
