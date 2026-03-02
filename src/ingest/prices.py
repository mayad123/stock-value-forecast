"""
Historical price ingestion: Alpha Vantage API -> raw JSON + incremental normalized store + manifest.
Each run fetches TIME_SERIES_DAILY compact (~100 points) per ticker and merges into ticker-level
history files (dedupe by date; newest value wins). The merged store is the canonical raw normalized
dataset for downstream feature building; multiple runs grow history beyond 100 days without premium.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow running from repo root
import sys
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.ingest.alphavantage import (  # noqa: E402
    AlphaVantageError,
    fetch_daily_raw,
    get_api_key,
    throttle_wait,
)


NORMALIZED_KEYS = ["ticker", "date", "open", "high", "low", "close", "adjusted_close", "volume"]


def _datetime_to_version(ts: datetime) -> str:
    """Stable version string for manifests and paths (filesystem-safe)."""
    return ts.strftime("%Y-%m-%dT%H-%M-%S")


def _parse_time_series(raw: Dict[str, Any], ticker: str) -> List[Dict[str, Any]]:
    """
    Extract daily OHLCV from Alpha Vantage raw response.
    Handles TIME_SERIES_DAILY (1–5: open, high, low, close, volume) and, for legacy raw files,
    TIME_SERIES_DAILY_ADJUSTED (5. adjusted close, 6. volume). For daily, adjusted_close = close.
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


def _read_normalized_csv(path: Path) -> List[Dict[str, Any]]:
    """Read normalized price CSV into list of dicts (same keys as NORMALIZED_KEYS)."""
    if not path.exists():
        return []
    rows = []
    with open(path) as f:
        f.readline()  # skip header
        for line in f:
            line = line.strip()
            if not line:
                continue
            values = _parse_csv_line(line)
            if len(values) >= len(NORMALIZED_KEYS):
                rows.append(dict(zip(NORMALIZED_KEYS, values[: len(NORMALIZED_KEYS)])))
    return rows


def _parse_csv_line(line: str) -> List[Any]:
    """Parse a single CSV line (handles quoted fields)."""
    out = []
    i = 0
    while i < len(line):
        if line[i] == '"':
            i += 1
            cell = []
            while i < len(line):
                if line[i] == '"':
                    i += 1
                    if i < len(line) and line[i] == '"':
                        cell.append('"')
                        i += 1
                    else:
                        break
                else:
                    cell.append(line[i])
                    i += 1
            out.append("".join(cell))
        else:
            start = i
            while i < len(line) and line[i] != ",":
                i += 1
            out.append(line[start:i].strip())
            i += 1
    return out


def _merge_ticker_history(
    existing: List[Dict[str, Any]], new_rows: List[Dict[str, Any]], ticker: str
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Merge new rows into existing (dedupe by date; keep most recent value per date).
    Returns (merged_rows sorted by date, number of new dates appended).
    """
    by_date: Dict[str, Dict[str, Any]] = {}
    for r in existing:
        by_date[r["date"]] = dict(r)
    existing_dates = set(by_date.keys())
    for r in new_rows:
        by_date[r["date"]] = dict(r)
    new_dates_appended = len(set(r["date"] for r in new_rows) - existing_dates)
    merged = sorted(by_date.values(), key=lambda x: x["date"])
    return merged, new_dates_appended


def run_ingest_prices(
    config: Dict[str, Any],
    data_raw_root: Optional[Path] = None,
    log: Optional[Any] = None,
) -> str:
    """
    Ingest daily OHLCV for all configured tickers via Alpha Vantage (compact only).
    - Saves raw API responses under data/raw/prices/{ticker}/{ingestion_timestamp}.json
    - Merges normalized rows into ticker-level history under data/raw/prices_normalized/{ticker}.csv
    - Saves manifest under data/raw/manifests/{dataset_version}.json with ticker_histories (status, new_rows)
    Returns dataset_version (ingestion timestamp string).
    """
    if config.get("mode") == "recruiter_demo":
        print("Demo mode uses sample data. Use live_apis mode for ingestion.", file=sys.stderr)
        sys.exit(1)

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

    raw_prices_dir = raw_root / "prices"
    normalized_dir = raw_root / "prices_normalized"
    manifests_dir = raw_root / "manifests"
    raw_prices_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    log(f"Dataset version: {dataset_version}")
    log(f"Tickers: {len(tickers)}")
    api_endpoint = "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&outputsize=compact"

    raw_paths: List[str] = []
    ticker_histories: List[Dict[str, Any]] = []
    all_dates: List[str] = []

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
            raw = fetch_daily_raw(symbol, api_key)
            with open(raw_path, "w") as f:
                json.dump(raw, f, indent=2)

        raw_paths.append(str(raw_path.relative_to(raw_root)))
        new_rows = _parse_time_series(raw, symbol)
        log(f"  {symbol}: {len(new_rows)} daily bars from API")

        history_path = normalized_dir / f"{symbol}.csv"
        existing = _read_normalized_csv(history_path)
        merged, new_rows_appended = _merge_ticker_history(existing, new_rows, symbol)
        status = "created" if not existing else "updated"
        _write_normalized_csv(merged, history_path)

        rel_path = str(history_path.relative_to(raw_root))
        ticker_histories.append({
            "ticker": symbol,
            "path": rel_path,
            "status": status,
            "new_rows": new_rows_appended,
            "total_rows": len(merged),
        })
        all_dates.extend(r["date"] for r in merged)

    normalized_paths = [h["path"] for h in ticker_histories]
    date_range = {"min": min(all_dates), "max": max(all_dates)} if all_dates else {}

    manifest = {
        "dataset_version": dataset_version,
        "ingestion_timestamp": ingestion_time.isoformat() + "Z",
        "api_endpoint": api_endpoint,
        "tickers": tickers,
        "date_range": date_range,
        "raw_paths": raw_paths,
        "normalized_paths": normalized_paths,
        "ticker_histories": ticker_histories,
    }

    # Optional enrichment (additive; not required for training)
    enrichment_cfg = config.get("enrichment") or {}
    if (
        enrichment_cfg.get("symbol_search")
        or enrichment_cfg.get("global_quote")
        or enrichment_cfg.get("weekly_monthly")
    ):
        try:
            from src.ingest.enrichment import run_enrichment
            enrichment_manifest = run_enrichment(
                config, raw_root, dataset_version, api_key, tickers, log=log
            )
            manifest.update(enrichment_manifest)
        except AlphaVantageError as e:
            log(f"Enrichment failed (non-fatal): {e}")
            manifest["enrichment"] = {"enrichment_error": str(e)}

    manifest_path = manifests_dir / f"{dataset_version}.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    log(f"Manifest: {manifest_path}")
    for h in ticker_histories:
        log(f"  {h['ticker']}: {h['status']}, +{h['new_rows']} rows, total {h['total_rows']}")
    return dataset_version


def _write_normalized_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    """Write normalized rows to CSV (no pandas required)."""
    if not rows:
        return
    with open(path, "w") as f:
        f.write(",".join(NORMALIZED_KEYS) + "\n")
        for r in rows:
            line = ",".join(_csv_cell(r.get(k)) for k in NORMALIZED_KEYS)
            f.write(line + "\n")


def _csv_cell(val: Any) -> str:
    if val is None:
        return ""
    s = str(val)
    if "," in s or '"' in s or "\n" in s:
        return '"' + s.replace('"', '""') + '"'
    return s
