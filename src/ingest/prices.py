"""
Historical price ingestion: Alpha Vantage API -> raw JSON + normalized table + manifest.
Raw responses are never overwritten; each run creates a new dataset version.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow running from repo root
import sys
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.ingest.alphavantage import (
    AlphaVantageError,
    fetch_daily_adjusted,
    get_api_key,
    throttle_wait,
)


def _datetime_to_version(ts: datetime) -> str:
    """Stable version string for manifests and paths (filesystem-safe)."""
    return ts.strftime("%Y-%m-%dT%H-%M-%S")


def _parse_time_series(raw: Dict[str, Any], ticker: str) -> List[Dict[str, Any]]:
    """
    Extract daily OHLCV from Alpha Vantage raw response.
    Handles both TIME_SERIES_DAILY (5. volume) and TIME_SERIES_DAILY_ADJUSTED (5. adjusted close, 6. volume).
    Returns list of dicts with keys: ticker, date, open, high, low, close, adjusted_close, volume.
    """
    series = raw.get("Time Series (Daily)")
    if not series:
        return []

    rows = []
    for date_str, day in series.items():
        open_ = day.get("1. open")
        high = day.get("2. high")
        low = day.get("3. low")
        close = day.get("4. close")
        adj_close = day.get("5. adjusted close") or close
        vol = day.get("6. volume") or day.get("5. volume")

        if open_ is None or close is None:
            continue
        try:
            rows.append({
                "ticker": ticker,
                "date": date_str,
                "open": float(open_),
                "high": float(high) if high else None,
                "low": float(low) if low else None,
                "close": float(close),
                "adjusted_close": float(adj_close) if adj_close else float(close),
                "volume": int(float(vol)) if vol else None,
            })
        except (TypeError, ValueError):
            continue
    return rows


def run_ingest_prices(
    config: Dict[str, Any],
    data_raw_root: Optional[Path] = None,
    log: Optional[Any] = None,
) -> str:
    """
    Ingest daily OHLCV for all configured tickers via Alpha Vantage.
    - Saves raw API responses under data/raw/prices/{ticker}/{ingestion_timestamp}.json
    - Saves normalized table under data/raw/prices_normalized/{dataset_version}/
    - Saves manifest under data/raw/manifests/{dataset_version}.json
    Returns dataset_version (ingestion timestamp string).
    """
    if log is None:
        def log(msg: str) -> None:
            print(f"[INGEST] {msg}")

    paths_cfg = config.get("paths", {})
    raw_root = data_raw_root or Path(paths_cfg.get("data_raw", "data/raw"))
    if not raw_root.is_absolute():
        raw_root = _REPO_ROOT / raw_root

    tickers = config.get("tickers", {}).get("symbols", [])
    if not tickers:
        raise ValueError("Config has no tickers.symbols")

    api_key = get_api_key()
    ingestion_time = datetime.utcnow()
    dataset_version = _datetime_to_version(ingestion_time)

    # Paths for this run (never overwrite existing raw files)
    raw_prices_dir = raw_root / "prices"
    normalized_dir = raw_root / "prices_normalized" / dataset_version
    manifests_dir = raw_root / "manifests"
    raw_prices_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    log(f"Dataset version: {dataset_version}")
    log(f"Tickers: {len(tickers)}")
    api_endpoint = "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY_ADJUSTED"

    raw_paths: List[str] = []
    all_rows: List[Dict[str, Any]] = []

    for i, symbol in enumerate(tickers):
        ticker_dir = raw_prices_dir / symbol
        ticker_dir.mkdir(parents=True, exist_ok=True)
        raw_path = ticker_dir / f"{dataset_version}.json"

        if raw_path.exists():
            log(f"Raw file already exists (skip fetch): {raw_path}")
            with open(raw_path) as f:
                raw = json.load(f)
        else:
            throttle_wait()
            log(f"Fetching {symbol} ({i + 1}/{len(tickers)})")
            raw = fetch_daily_adjusted(symbol, api_key, outputsize="full")
            with open(raw_path, "w") as f:
                json.dump(raw, f, indent=2)

        raw_paths.append(str(raw_path.relative_to(raw_root)))
        rows = _parse_time_series(raw, symbol)
        all_rows.extend(rows)
        log(f"  {symbol}: {len(rows)} daily bars")

    # Optional: filter by config date range
    time_horizon = config.get("time_horizon", {})
    ingest_start = time_horizon.get("ingest_start")
    ingest_end = time_horizon.get("train_end") or time_horizon.get("test_start")
    if ingest_start or ingest_end:
        filtered = []
        for r in all_rows:
            d = r["date"]
            if ingest_start and d < ingest_start:
                continue
            if ingest_end and d > ingest_end:
                continue
            filtered.append(r)
        all_rows = filtered
        log(f"Filtered by date range: {len(all_rows)} rows")

    # Sort by date for stable output
    all_rows.sort(key=lambda r: (r["ticker"], r["date"]))

    # Save normalized (CSV for minimal deps; Parquet optional later)
    normalized_file = normalized_dir / "prices.csv"
    if all_rows:
        _write_normalized_csv(all_rows, normalized_file)
    normalized_paths = [str(normalized_file.relative_to(raw_root))] if all_rows else []

    date_range = (
        {"min": min(r["date"] for r in all_rows), "max": max(r["date"] for r in all_rows)}
        if all_rows
        else {}
    )

    manifest = {
        "dataset_version": dataset_version,
        "ingestion_timestamp": ingestion_time.isoformat() + "Z",
        "api_endpoint": api_endpoint,
        "tickers": tickers,
        "date_range": date_range,
        "raw_paths": raw_paths,
        "normalized_paths": normalized_paths,
    }
    manifest_path = manifests_dir / f"{dataset_version}.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    log(f"Manifest: {manifest_path}")
    log(f"Normalized: {normalized_dir}")
    return dataset_version


def _write_normalized_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    """Write normalized rows to CSV (no pandas required)."""
    if not rows:
        return
    keys = ["ticker", "date", "open", "high", "low", "close", "adjusted_close", "volume"]
    with open(path, "w") as f:
        f.write(",".join(keys) + "\n")
        for r in rows:
            line = ",".join(_csv_cell(r.get(k)) for k in keys)
            f.write(line + "\n")


def _csv_cell(val: Any) -> str:
    if val is None:
        return ""
    s = str(val)
    if "," in s or '"' in s or "\n" in s:
        return '"' + s.replace('"', '""') + '"'
    return s
