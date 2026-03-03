"""
Validate every ticker CSV in data/sample/prices_normalized/ (or config data_raw) against the
repo normalized schema and time-series assumptions. Optionally correct descending dates to
ascending; fail on unsorted/duplicates or missing/invalid numerics. Write a summary artifact
to reports/data_validation_<dataset_version>.json.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

REQUIRED_COLUMNS = [
    "ticker",
    "date",
    "open",
    "high",
    "low",
    "close",
    "adjusted_close",
    "volume",
]

NUMERIC_COLUMNS = ["open", "high", "low", "close", "adjusted_close", "volume"]


class ValidationError(Exception):
    """Raised when a CSV fails validation (missing columns, bad dates, duplicates, invalid numerics)."""
    pass


def _parse_dates_yyyy_mm_dd(df: pd.DataFrame, path: Path) -> pd.DataFrame:
    """Parse date column as YYYY-MM-DD; normalize to string. Raises ValidationError on invalid dates."""
    if "date" not in df.columns:
        raise ValidationError(f"{path.name}: missing column 'date'")
    try:
        dt = pd.to_datetime(df["date"], format="mixed", errors="coerce")
    except Exception as e:
        raise ValidationError(f"{path.name}: could not parse 'date' as YYYY-MM-DD: {e}") from e
    if dt.isna().any():
        bad = df.loc[dt.isna(), "date"]
        rows = bad.index.tolist()[:5]
        raise ValidationError(
            f"{path.name}: invalid or missing date at row(s) {rows}. Values: {bad.iloc[:5].tolist()}"
        )
    df = df.copy()
    df["date"] = dt.dt.strftime("%Y-%m-%d")
    return df


def _check_duplicates(df: pd.DataFrame, path: Path) -> None:
    """Raise ValidationError if duplicate (ticker, date) rows exist."""
    dup = df.duplicated(subset=["ticker", "date"], keep=False)
    if dup.any():
        n = dup.sum()
        examples = df.loc[dup].head(3)[["ticker", "date"]].to_dict("records")
        raise ValidationError(
            f"{path.name}: duplicate (ticker, date) rows ({n} rows). "
            f"Example: {examples}. Remove duplicates or consolidate rows."
        )


def _ordering_status(dates: pd.Series) -> str:
    """Return 'ascending' | 'descending' | 'unsorted'."""
    if len(dates) <= 1:
        return "ascending"
    vals = dates.astype(str).tolist()
    if all(vals[i] < vals[i + 1] for i in range(len(vals) - 1)):
        return "ascending"
    if all(vals[i] > vals[i + 1] for i in range(len(vals) - 1)):
        return "descending"
    return "unsorted"


def _check_numeric_no_missing(df: pd.DataFrame, path: Path) -> None:
    """Raise ValidationError if required numeric columns have missing or unparseable values."""
    for col in NUMERIC_COLUMNS:
        if col not in df.columns:
            raise ValidationError(f"{path.name}: missing required column '{col}'")
        try:
            ser = pd.to_numeric(df[col], errors="coerce")
        except Exception as e:
            raise ValidationError(f"{path.name}: column '{col}' could not be parsed as numeric: {e}") from e
        if ser.isna().any():
            bad = df.loc[ser.isna()].head(3)
            rows = bad.index.tolist()
            raise ValidationError(
                f"{path.name}: missing or non-numeric value(s) in column '{col}' at row(s) {rows}. "
                f"Example: {bad[['date', col]].to_dict('records')}"
            )


def _process_one(path: Path, log: Any, write_corrected: bool = True) -> Dict[str, Any]:
    """
    Validate one CSV; if dates are strictly descending, reverse to ascending and optionally write back.
    Returns dict with ticker, row_count, min_date, max_date, corrected (bool).
    Raises ValidationError on missing columns, unsorted/duplicate dates, or invalid numerics.
    """
    df = pd.read_csv(path)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValidationError(f"{path.name}: missing required columns: {missing}.")

    df = _parse_dates_yyyy_mm_dd(df, path)
    _check_duplicates(df, path)
    _check_numeric_no_missing(df, path)

    statuses: List[str] = []
    for _ticker, group in df.groupby("ticker", sort=False):
        statuses.append(_ordering_status(group["date"]))

    if any(s == "unsorted" for s in statuses):
        raise ValidationError(
            f"{path.name}: dates are not strictly ascending or descending (unsorted or duplicate dates). "
            "Fix ordering or remove duplicates."
        )
    if any(s == "ascending" for s in statuses) and any(s == "descending" for s in statuses):
        raise ValidationError(
            f"{path.name}: mixed ordering (some tickers ascending, some descending). "
            "Use a single order (oldest→newest or newest→oldest) per file."
        )

    corrected = False
    if all(s == "descending" for s in statuses):
        out_parts = []
        for ticker, group in df.groupby("ticker", sort=False):
            out_parts.append(group.iloc[::-1].reset_index(drop=True))
        df = pd.concat(out_parts, ignore_index=True).sort_values(["ticker", "date"]).reset_index(drop=True)
        if write_corrected:
            df.to_csv(path, index=False)
            log(f"  {path.name}: was descending, reversed and written.")
        corrected = True
    elif all(s == "ascending" for s in statuses):
        log(f"  {path.name}: already ascending, no change.")

    ticker = path.stem
    dates = df["date"].astype(str)
    min_d = dates.min()
    max_d = dates.max()
    return {
        "ticker": ticker,
        "path": str(path.name),
        "row_count": len(df),
        "min_date": min_d,
        "max_date": max_d,
        "corrected": corrected,
    }


def run_validate_prices(
    config: Dict[str, Any],
    raw_root: Optional[Path] = None,
    reports_path: Optional[Path] = None,
    dataset_version: Optional[str] = None,
    write_corrected: bool = True,
    log: Any = None,
) -> Path:
    """
    Validate every CSV in raw_root / prices_normalized/. Correct descending dates to ascending
    when write_corrected is True. Write summary to reports_path / data_validation_<version>.json.
    Returns the path to the summary artifact. Raises ValidationError on any failure.
    """
    if log is None:
        def log(msg: str) -> None:
            print(f"[VALIDATE-PRICES] {msg}")

    paths_cfg = config.get("paths", {})
    repo_root = Path(__file__).resolve().parents[2]
    raw_root = raw_root or (repo_root / paths_cfg.get("data_raw", "data/sample"))
    if not raw_root.is_absolute():
        raw_root = repo_root / raw_root
    raw_root = raw_root.resolve()

    reports_path = reports_path or (repo_root / "reports")
    reports_path = reports_path.resolve()
    reports_path.mkdir(parents=True, exist_ok=True)

    version = dataset_version or config.get("feature_build", {}).get("raw_dataset_version", "demo")
    prices_dir = raw_root / "prices_normalized"
    if not prices_dir.is_dir():
        raise ValidationError(f"Prices directory not found: {prices_dir}")

    csv_files = sorted(prices_dir.glob("*.csv"))
    if not csv_files:
        raise ValidationError(f"No *.csv under {prices_dir}")

    log(f"Validating {len(csv_files)} CSV(s) under {prices_dir}")
    results: List[Dict[str, Any]] = []
    for path in csv_files:
        results.append(_process_one(path, log, write_corrected=write_corrected))

    tickers = sorted(r["ticker"] for r in results)
    all_min = [r["min_date"] for r in results]
    all_max = [r["max_date"] for r in results]
    summary = {
        "dataset_version": version,
        "tickers": tickers,
        "file_count": len(results),
        "row_counts": {r["ticker"]: r["row_count"] for r in results},
        "date_ranges": {r["ticker"]: {"min": r["min_date"], "max": r["max_date"]} for r in results},
        "global_date_range": {"min": min(all_min), "max": max(all_max)} if all_min and all_max else {},
        "per_file": results,
    }

    out_path = reports_path / f"data_validation_{version}.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    log(f"Wrote {out_path}")
    return out_path
