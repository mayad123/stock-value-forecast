"""
Generate a price manifest by scanning data/sample/prices_normalized/ (or config data_raw).

Use this to avoid manually editing manifests when adding ticker CSVs.
Run: python run.py manifest [VERSION]   (e.g. python run.py manifest demo)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# Required date column for computing global range
DATE_COL = "date"


def _scan_csv_dates(path: Path) -> Tuple[str, int, Optional[str], Optional[str]]:
    """
    Read a CSV and return (ticker, row_count, min_date, max_date).
    Ticker is inferred from stem (e.g. AAPL.csv -> AAPL). Dates from DATE_COL.
    """
    df = pd.read_csv(path)
    if DATE_COL not in df.columns:
        raise ValueError(f"{path.name}: missing column '{DATE_COL}'")
    ticker = path.stem
    dt = pd.to_datetime(df[DATE_COL], format="mixed", errors="coerce")
    valid = dt.dropna()
    if valid.empty:
        return ticker, len(df), None, None
    min_d = valid.min().strftime("%Y-%m-%d")
    max_d = valid.max().strftime("%Y-%m-%d")
    return ticker, len(df), min_d, max_d


def generate_manifest(
    raw_root: Path,
    dataset_version: str,
    prices_subdir: str = "prices_normalized",
    log: Any = None,
) -> Path:
    """
    Scan raw_root / prices_subdir for *.csv, build manifest with dataset_version,
    normalized_paths, global date_range, and tickers. Write to raw_root/manifests/{version}.json.
    Returns the manifest path. All referenced paths are verified to exist.
    """
    if log is None:
        def log(msg: str) -> None:
            print(f"[MANIFEST] {msg}")

    raw_root = Path(raw_root).resolve()
    prices_dir = raw_root / prices_subdir
    if not prices_dir.is_dir():
        raise FileNotFoundError(f"Prices directory not found: {prices_dir}")

    csv_files = sorted(prices_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No *.csv under {prices_dir}")

    normalized_paths: List[str] = []
    tickers: List[str] = []
    ticker_histories: List[Dict[str, Any]] = []
    all_min: List[str] = []
    all_max: List[str] = []

    for path in csv_files:
        rel = path.relative_to(raw_root)
        rel_str = str(rel).replace("\\", "/")
        ticker, total_rows, min_d, max_d = _scan_csv_dates(path)
        normalized_paths.append(rel_str)
        tickers.append(ticker)
        ticker_histories.append({
            "ticker": ticker,
            "path": rel_str,
            "status": "included",
            "total_rows": total_rows,
        })
        if min_d is not None:
            all_min.append(min_d)
        if max_d is not None:
            all_max.append(max_d)

    # Deduplicate and sort tickers for traceability
    tickers = sorted(set(tickers))

    if not all_min or not all_max:
        raise ValueError("No valid dates found in any CSV; cannot compute date_range.")

    date_range = {"min": min(all_min), "max": max(all_max)}

    manifest = {
        "dataset_version": dataset_version,
        "ingestion_timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "api_endpoint": "offline_sample",
        "tickers": tickers,
        "date_range": date_range,
        "raw_paths": [],
        "normalized_paths": normalized_paths,
        "ticker_histories": ticker_histories,
    }

    manifests_dir = raw_root / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifests_dir / f"{dataset_version}.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    log(f"Wrote {manifest_path} ({len(normalized_paths)} paths, date_range {date_range})")
    return manifest_path
