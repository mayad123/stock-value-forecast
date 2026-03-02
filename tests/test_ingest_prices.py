"""Tests for price ingestion (mocked API)."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.ingest.alphavantage import AlphaVantageError, get_api_key, fetch_daily_raw
from src.ingest.prices import (
    _merge_ticker_history,
    _parse_time_series,
    run_ingest_prices,
)


def test_get_api_key_missing():
    with patch.dict(os.environ, {}, clear=False):
        if "ALPHAVANTAGE_API_KEY" in os.environ:
            del os.environ["ALPHAVANTAGE_API_KEY"]
        try:
            get_api_key()
            assert False, "expected AlphaVantageError"
        except AlphaVantageError as e:
            assert "ALPHAVANTAGE_API_KEY" in str(e)


def test_parse_time_series_daily():
    """Parse TIME_SERIES_DAILY (free tier): 1–5 = open, high, low, close, volume; adjusted_close = close."""
    raw = {
        "Time Series (Daily)": {
            "2024-01-15": {
                "1. open": "185.0",
                "2. high": "186.5",
                "3. low": "184.0",
                "4. close": "188.0",
                "5. volume": "1000000",
            },
            "2024-01-14": {
                "1. open": "184.0",
                "2. high": "185.0",
                "3. low": "183.0",
                "4. close": "184.5",
                "5. volume": "900000",
            },
        }
    }
    rows = _parse_time_series(raw, "AAPL")
    assert len(rows) == 2
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["date"] == "2024-01-15"
    assert rows[0]["open"] == 185.0
    assert rows[0]["close"] == 188.0
    assert rows[0]["adjusted_close"] == 188.0  # falls back to close for TIME_SERIES_DAILY
    assert rows[0]["volume"] == 1000000


def test_fetch_daily_raw_rejects_premium_response():
    """If API returns premium-endpoint message (e.g. wrong function), we raise and never use it."""
    premium_body = {"Information": "Thank you for using Alpha Vantage! This is a premium endpoint."}
    with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "test-key"}):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock_urlopen.return_value.__enter__.return_value
            mock_resp.read.return_value = json.dumps(premium_body).encode("utf-8")
            try:
                fetch_daily_raw("AAPL", "test-key")
                assert False, "expected AlphaVantageError"
            except AlphaVantageError as e:
                assert "premium" in str(e).lower()


def test_run_ingest_prices_mocked():
    """Run full pipeline with mocked API (free-tier TIME_SERIES_DAILY); check raw JSON, normalized CSV, manifest."""
    mock_response = {
        "Meta Data": {"2. Symbol": "AAPL"},
        "Time Series (Daily)": {
            "2024-01-02": {
                "1. open": "185.0",
                "2. high": "186.0",
                "3. low": "184.0",
                "4. close": "185.5",
                "5. volume": "5000000",
            },
        },
    }

    with tempfile.TemporaryDirectory() as tmp:
        raw_root = Path(tmp)
        config = {
            "paths": {"data_raw": str(raw_root)},
            "tickers": {"symbols": ["AAPL"]},
            "time_horizon": {},
        }

        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "test-key"}):
            with patch("src.ingest.prices.fetch_daily_raw", return_value=mock_response):
                with patch("src.ingest.prices.throttle_wait"):
                    version = run_ingest_prices(config, data_raw_root=raw_root)

        assert version
        raw_path = raw_root / "prices" / "AAPL" / f"{version}.json"
        assert raw_path.exists()
        with open(raw_path) as f:
            saved_raw = json.load(f)
        assert saved_raw == mock_response

        manifest_path = raw_root / "manifests" / f"{version}.json"
        assert manifest_path.exists()
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert manifest["dataset_version"] == version
        assert manifest["tickers"] == ["AAPL"]
        assert "raw_paths" in manifest
        assert "normalized_paths" in manifest
        assert "api_endpoint" in manifest
        assert "TIME_SERIES_DAILY" in manifest["api_endpoint"]
        assert "compact" in manifest["api_endpoint"]
        assert "ingestion_timestamp" in manifest
        assert "ticker_histories" in manifest
        histories = manifest["ticker_histories"]
        assert len(histories) == 1
        assert histories[0]["ticker"] == "AAPL"
        assert histories[0]["status"] == "created"
        assert histories[0]["new_rows"] == 1
        assert histories[0]["total_rows"] == 1

        csv_path = raw_root / "prices_normalized" / "AAPL.csv"
        assert csv_path.exists()
        content = csv_path.read_text()
        assert "ticker,date,open,high,low,close,adjusted_close,volume" in content
        assert "AAPL,2024-01-02" in content


def test_merge_ticker_history_dedupe_by_date():
    """Merge keeps one row per date; new overwrites existing."""
    existing = [
        {"ticker": "AAPL", "date": "2024-01-01", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "adjusted_close": 100.5, "volume": 1},
        {"ticker": "AAPL", "date": "2024-01-02", "open": 101.0, "high": 102.0, "low": 100.0, "close": 101.5, "adjusted_close": 101.5, "volume": 2},
    ]
    new_rows = [
        {"ticker": "AAPL", "date": "2024-01-02", "open": 101.1, "high": 102.1, "low": 100.1, "close": 101.6, "adjusted_close": 101.6, "volume": 3},
        {"ticker": "AAPL", "date": "2024-01-03", "open": 102.0, "high": 103.0, "low": 101.0, "close": 102.5, "adjusted_close": 102.5, "volume": 4},
    ]
    merged, new_appended = _merge_ticker_history(existing, new_rows, "AAPL")
    assert len(merged) == 3
    assert merged[0]["date"] == "2024-01-01"
    assert merged[1]["date"] == "2024-01-02"
    assert merged[1]["close"] == 101.6  # new overwrote
    assert merged[2]["date"] == "2024-01-03"
    assert new_appended == 1  # only 2024-01-03 was new


def test_ingest_second_run_merges_and_grows_history():
    """Second run updates ticker history; total rows can grow beyond 100 without full/outputsize=full."""
    from datetime import datetime
    mock_run1 = {
        "Meta Data": {"2. Symbol": "AAPL"},
        "Time Series (Daily)": {
            "2024-01-02": {"1. open": "185.0", "2. high": "186.0", "3. low": "184.0", "4. close": "185.5", "5. volume": "5000000"},
            "2024-01-01": {"1. open": "184.0", "2. high": "185.0", "3. low": "183.0", "4. close": "184.5", "5. volume": "4000000"},
        },
    }
    mock_run2 = {
        "Meta Data": {"2. Symbol": "AAPL"},
        "Time Series (Daily)": {
            "2024-01-03": {"1. open": "186.0", "2. high": "187.0", "3. low": "185.0", "4. close": "186.5", "5. volume": "6000000"},
            "2024-01-02": {"1. open": "185.1", "2. high": "186.1", "3. low": "184.1", "4. close": "185.6", "5. volume": "5100000"},
        },
    }

    with tempfile.TemporaryDirectory() as tmp:
        raw_root = Path(tmp)
        config = {"paths": {"data_raw": str(raw_root)}, "tickers": {"symbols": ["AAPL"]}, "time_horizon": {}}
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "k"}):
            with patch("src.ingest.prices.throttle_wait"):
                with patch("src.ingest.prices.fetch_daily_raw", return_value=mock_run1):
                    with patch("src.ingest.prices.datetime") as mock_dt:
                        mock_dt.utcnow.return_value = datetime(2024, 6, 1, 12, 0, 0)
                        v1 = run_ingest_prices(config, data_raw_root=raw_root)
                with patch("src.ingest.prices.fetch_daily_raw", return_value=mock_run2):
                    with patch("src.ingest.prices.datetime") as mock_dt:
                        mock_dt.utcnow.return_value = datetime(2024, 6, 2, 12, 0, 0)
                        v2 = run_ingest_prices(config, data_raw_root=raw_root)

        assert v1 != v2
        csv_path = raw_root / "prices_normalized" / "AAPL.csv"
        lines = csv_path.read_text().strip().split("\n")
        assert len(lines) >= 4  # header + 3 unique dates (01-01, 01-02, 01-03)
        with open(raw_root / "manifests" / f"{v2}.json") as f:
            m2 = json.load(f)
        hist = m2["ticker_histories"][0]
        assert hist["status"] == "updated"
        assert hist["total_rows"] == 3
        assert hist["new_rows"] == 1  # 2024-01-03 was new


def test_ingest_with_enrichment_enabled_adds_enrichment_to_manifest():
    """When enrichment is enabled, manifest records which enrichment data was collected."""
    mock_response = {
        "Meta Data": {"2. Symbol": "AAPL"},
        "Time Series (Daily)": {
            "2024-01-02": {"1. open": "185.0", "2. high": "186.0", "3. low": "184.0", "4. close": "185.5", "5. volume": "5000000"},
        },
    }
    enrichment_result = {"enrichment": {"symbol_search": {"enabled": True, "path": "enrichment/symbol_search/v.json", "keywords": "stock"}}}

    with tempfile.TemporaryDirectory() as tmp:
        raw_root = Path(tmp)
        config = {
            "paths": {"data_raw": str(raw_root)},
            "tickers": {"symbols": ["AAPL"]},
            "time_horizon": {},
            "enrichment": {"symbol_search": True, "global_quote": False, "weekly_monthly": False, "symbol_search_keywords": "stock"},
        }
        with patch.dict(os.environ, {"ALPHAVANTAGE_API_KEY": "k"}):
            with patch("src.ingest.prices.fetch_daily_raw", return_value=mock_response):
                with patch("src.ingest.prices.throttle_wait"):
                    with patch("src.ingest.enrichment.run_enrichment", return_value=enrichment_result):
                        version = run_ingest_prices(config, data_raw_root=raw_root)
        with open(raw_root / "manifests" / f"{version}.json") as f:
            manifest = json.load(f)
        assert "enrichment" in manifest
        assert manifest["enrichment"]["symbol_search"]["enabled"] is True
        assert "path" in manifest["enrichment"]["symbol_search"]
