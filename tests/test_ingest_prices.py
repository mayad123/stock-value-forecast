"""Tests for price ingestion (mocked API)."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.ingest.alphavantage import AlphaVantageError, get_api_key
from src.ingest.prices import _parse_time_series, run_ingest_prices


def test_get_api_key_missing():
    with patch.dict(os.environ, {}, clear=False):
        if "ALPHAVANTAGE_API_KEY" in os.environ:
            del os.environ["ALPHAVANTAGE_API_KEY"]
        try:
            get_api_key()
            assert False, "expected AlphaVantageError"
        except AlphaVantageError as e:
            assert "ALPHAVANTAGE_API_KEY" in str(e)


def test_parse_time_series_daily_adjusted():
    raw = {
        "Time Series (Daily)": {
            "2024-01-15": {
                "1. open": "185.0",
                "2. high": "186.5",
                "3. low": "184.0",
                "4. close": "188.0",
                "5. adjusted close": "188.0",
                "6. volume": "1000000",
            },
            "2024-01-14": {
                "1. open": "184.0",
                "2. high": "185.0",
                "3. low": "183.0",
                "4. close": "184.5",
                "5. adjusted close": "184.5",
                "6. volume": "900000",
            },
        }
    }
    rows = _parse_time_series(raw, "AAPL")
    assert len(rows) == 2
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["date"] == "2024-01-15"
    assert rows[0]["open"] == 185.0
    assert rows[0]["close"] == 188.0
    assert rows[0]["adjusted_close"] == 188.0
    assert rows[0]["volume"] == 1000000


def test_run_ingest_prices_mocked():
    """Run full pipeline with mocked API; check raw JSON, normalized CSV, manifest."""
    mock_response = {
        "Meta Data": {"2. Symbol": "AAPL"},
        "Time Series (Daily)": {
            "2024-01-02": {
                "1. open": "185.0",
                "2. high": "186.0",
                "3. low": "184.0",
                "4. close": "185.5",
                "5. adjusted close": "185.5",
                "6. volume": "5000000",
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
            with patch("src.ingest.prices.fetch_daily_adjusted", return_value=mock_response):
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
        assert "ingestion_timestamp" in manifest

        norm_dir = raw_root / "prices_normalized" / version
        assert norm_dir.exists()
        csv_path = norm_dir / "prices.csv"
        assert csv_path.exists()
        content = csv_path.read_text()
        assert "ticker,date,open,high,low,close,adjusted_close,volume" in content
        assert "AAPL,2024-01-02" in content
