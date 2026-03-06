"""
Unit tests for ingestion output schema: normalized CSV columns and manifest keys.
Ensures pipeline contracts for downstream feature and train stages.
"""

import json
from pathlib import Path
from unittest.mock import patch

# Required columns in price normalized CSV (from src/ingest/prices._write_normalized_csv)
PRICE_NORMALIZED_COLUMNS = [
    "ticker", "date", "open", "high", "low", "close", "adjusted_close", "volume",
]

# Required keys in price manifest (from run_ingest_prices)
PRICE_MANIFEST_KEYS = [
    "dataset_version", "ingestion_timestamp", "api_endpoint", "tickers",
    "date_range", "raw_paths", "normalized_paths", "ticker_histories",
]

# Required columns in news normalized CSV (from src/ingest/news)
NEWS_NORMALIZED_COLUMNS = [
    "ticker", "publication_timestamp", "headline", "source",
    "sentiment_score", "match_score", "relevance_score", "article_uuid", "url",
]

# Required keys in news manifest
NEWS_MANIFEST_KEYS = [
    "dataset_version", "ingestion_timestamp", "api_endpoint", "tickers",
    "date_range", "published_after", "published_before", "raw_paths", "normalized_paths",
]


def test_price_normalized_csv_has_required_columns():
    """Price normalized output must have schema expected by feature pipeline."""
    import os
    import tempfile
    from src.ingest.prices import run_ingest_prices
    raw_root = Path(tempfile.mkdtemp())
    try:
        mock_response = {
            "Meta Data": {},
            "Time Series (Daily)": {
                "2024-01-02": {
                    "1. open": "100", "2. high": "101", "3. low": "99",
                    "4. close": "100.5", "5. volume": "1000000",
                },
            },
        }
        config = {
            "paths": {"data_raw": str(raw_root)},
            "tickers": {"symbols": ["AAPL"]},
            "time_horizon": {},
        }
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "k"}):
            with patch("src.ingest.prices.fetch_daily_raw", return_value=mock_response):
                with patch("src.ingest.prices.throttle_wait"):
                    run_ingest_prices(config, data_raw_root=raw_root)
        csv_path = raw_root / "prices_normalized" / "AAPL.csv"
        assert csv_path.exists()
        header = csv_path.read_text().split("\n")[0]
        got_columns = [c.strip() for c in header.split(",")]
        for col in PRICE_NORMALIZED_COLUMNS:
            assert col in got_columns, f"Price normalized CSV must have column '{col}'"
    finally:
        import shutil
        if raw_root.exists():
            shutil.rmtree(raw_root, ignore_errors=True)


def test_price_manifest_has_required_keys():
    """Price manifest must contain keys required for versioning and paths."""
    import os
    import tempfile
    from src.ingest.prices import run_ingest_prices
    raw_root = Path(tempfile.mkdtemp())
    try:
        mock_response = {
            "Meta Data": {},
            "Time Series (Daily)": {
                "2024-01-02": {
                    "1. open": "100", "2. high": "101", "3. low": "99",
                    "4. close": "100.5", "5. volume": "1000000",
                },
            },
        }
        config = {
            "paths": {"data_raw": str(raw_root)},
            "tickers": {"symbols": ["AAPL"]},
            "time_horizon": {},
        }
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "k"}):
            with patch("src.ingest.prices.fetch_daily_raw", return_value=mock_response):
                with patch("src.ingest.prices.throttle_wait"):
                    version = run_ingest_prices(config, data_raw_root=raw_root)
        manifest_path = raw_root / "manifests" / f"{version}.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        for key in PRICE_MANIFEST_KEYS:
            assert key in manifest, f"Price manifest must have key '{key}'"
    finally:
        import shutil
        if raw_root.exists():
            shutil.rmtree(raw_root, ignore_errors=True)


def test_news_normalized_csv_has_required_columns():
    """News normalized output must have columns expected by sentiment pipeline."""
    from src.ingest.news import run_ingest_news
    import tempfile
    raw_root = Path(tempfile.mkdtemp())
    try:
        config = {
            "paths": {"data_raw": str(raw_root)},
            "tickers": {"symbols": ["AAPL"]},
            "time_horizon": {},
            "news_ingest": {"limit": 5, "max_pages": 1},
        }
        mock_response = {
            "meta": {"returned": 1, "limit": 5},
            "data": [{
                "uuid": "u1",
                "title": "Head",
                "published_at": "2024-02-01T12:00:00Z",
                "source": "s.com",
                "entities": [{"symbol": "AAPL", "sentiment_score": 0.1, "match_score": 10}],
            }],
        }
        with patch("src.ingest.news.get_api_key", return_value="k"):
            with patch("src.ingest.news.fetch_news", return_value=mock_response):
                with patch("src.ingest.news.throttle_wait"):
                    version = run_ingest_news(config, data_raw_root=raw_root)
        csv_path = raw_root / "news_normalized" / version / "news.csv"
        assert csv_path.exists()
        header = csv_path.read_text().split("\n")[0]
        got_columns = [c.strip() for c in header.split(",")]
        for col in NEWS_NORMALIZED_COLUMNS:
            assert col in got_columns, f"News normalized CSV must have column '{col}'"
    finally:
        import shutil
        if raw_root.exists():
            shutil.rmtree(raw_root, ignore_errors=True)


def test_news_manifest_has_required_keys():
    """News manifest must contain keys for versioning and date range."""
    from src.ingest.news import run_ingest_news
    import tempfile
    raw_root = Path(tempfile.mkdtemp())
    try:
        config = {
            "paths": {"data_raw": str(raw_root)},
            "tickers": {"symbols": ["AAPL"]},
            "time_horizon": {},
            "news_ingest": {"limit": 5, "max_pages": 1},
        }
        mock_response = {"meta": {"returned": 0}, "data": []}
        with patch("src.ingest.news.get_api_key", return_value="k"):
            with patch("src.ingest.news.fetch_news", return_value=mock_response):
                with patch("src.ingest.news.throttle_wait"):
                    version = run_ingest_news(config, data_raw_root=raw_root)
        manifest_path = raw_root / "manifests" / f"news_{version}.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        for key in NEWS_MANIFEST_KEYS:
            assert key in manifest, f"News manifest must have key '{key}'"
    finally:
        import shutil
        if raw_root.exists():
            shutil.rmtree(raw_root, ignore_errors=True)
