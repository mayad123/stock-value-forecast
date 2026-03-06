"""
Optional Alpha Vantage enrichment: SYMBOL_SEARCH, GLOBAL_QUOTE, weekly/monthly time series.
Additive only; not required for training. All endpoints are free-tier (non-premium per official docs).
Controlled by config enrichment.* flags; manifests record which enrichment data was collected.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.ingest.alphavantage import (
    AlphaVantageError,
    fetch_global_quote,
    fetch_monthly,
    fetch_symbol_search,
    fetch_weekly,
    throttle_wait,
)


def run_enrichment(
    config: Dict[str, Any],
    raw_root: Path,
    dataset_version: str,
    api_key: str,
    tickers: List[str],
    log: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Run enabled enrichment calls; save raw JSON under data/raw/enrichment/...; return manifest fragment.
    Returns dict with key "enrichment" suitable for merging into the main ingest manifest.
    """
    if log is None:
        from src.logging_config import get_logger
        _log = get_logger("ingest")
        def log(msg: str) -> None:
            _log.info("%s", msg)

    enrichment_cfg = config.get("enrichment") or {}
    symbol_search_enabled = enrichment_cfg.get("symbol_search") is True
    global_quote_enabled = enrichment_cfg.get("global_quote") is True
    weekly_monthly_enabled = enrichment_cfg.get("weekly_monthly") is True
    keywords = enrichment_cfg.get("symbol_search_keywords", "stock")

    out: Dict[str, Any] = {
        "symbol_search": None,
        "global_quote": None,
        "weekly": None,
        "monthly": None,
    }

    enrichment_dir = raw_root / "enrichment"
    enrichment_dir.mkdir(parents=True, exist_ok=True)

    # SYMBOL_SEARCH: one request per run
    if symbol_search_enabled:
        try:
            throttle_wait()
            log("Enrichment: fetching SYMBOL_SEARCH")
            data = fetch_symbol_search(keywords, api_key)
            subdir = enrichment_dir / "symbol_search"
            subdir.mkdir(parents=True, exist_ok=True)
            path = subdir / f"{dataset_version}.json"
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            out["symbol_search"] = {
                "enabled": True,
                "path": str(path.relative_to(raw_root)),
                "keywords": keywords,
            }
        except AlphaVantageError as e:
            log(f"Enrichment SYMBOL_SEARCH failed: {e}")
            out["symbol_search"] = {"enabled": True, "error": str(e)}

    # GLOBAL_QUOTE: one request per ticker
    if global_quote_enabled and tickers:
        paths: List[str] = []
        version_dir = enrichment_dir / "global_quote" / dataset_version
        version_dir.mkdir(parents=True, exist_ok=True)
        for i, symbol in enumerate(tickers):
            try:
                throttle_wait()
                log(f"Enrichment: GLOBAL_QUOTE {symbol} ({i + 1}/{len(tickers)})")
                data = fetch_global_quote(symbol, api_key)
                path = version_dir / f"{symbol}.json"
                with open(path, "w") as f:
                    json.dump(data, f, indent=2)
                paths.append(str(path.relative_to(raw_root)))
            except AlphaVantageError as e:
                log(f"Enrichment GLOBAL_QUOTE {symbol} failed: {e}")
        out["global_quote"] = {"enabled": True, "path": str(version_dir.relative_to(raw_root)), "symbols": tickers, "paths": paths}

    # TIME_SERIES_WEEKLY: one per ticker
    if weekly_monthly_enabled and tickers:
        version_dir = enrichment_dir / "weekly" / dataset_version
        version_dir.mkdir(parents=True, exist_ok=True)
        paths: List[str] = []
        for i, symbol in enumerate(tickers):
            try:
                throttle_wait()
                log(f"Enrichment: WEEKLY {symbol} ({i + 1}/{len(tickers)})")
                data = fetch_weekly(symbol, api_key)
                path = version_dir / f"{symbol}.json"
                with open(path, "w") as f:
                    json.dump(data, f, indent=2)
                paths.append(str(path.relative_to(raw_root)))
            except AlphaVantageError as e:
                log(f"Enrichment WEEKLY {symbol} failed: {e}")
        out["weekly"] = {"enabled": True, "path": str(version_dir.relative_to(raw_root)), "symbols": tickers, "paths": paths}

    # TIME_SERIES_MONTHLY: one per ticker
    if weekly_monthly_enabled and tickers:
        version_dir = enrichment_dir / "monthly" / dataset_version
        version_dir.mkdir(parents=True, exist_ok=True)
        monthly_paths: List[str] = []
        for i, symbol in enumerate(tickers):
            try:
                throttle_wait()
                log(f"Enrichment: MONTHLY {symbol} ({i + 1}/{len(tickers)})")
                data = fetch_monthly(symbol, api_key)
                path = version_dir / f"{symbol}.json"
                with open(path, "w") as f:
                    json.dump(data, f, indent=2)
                monthly_paths.append(str(path.relative_to(raw_root)))
            except AlphaVantageError as e:
                log(f"Enrichment MONTHLY {symbol} failed: {e}")
        out["monthly"] = {"enabled": True, "path": str(version_dir.relative_to(raw_root)), "symbols": tickers, "paths": monthly_paths}

    return {"enrichment": out}
