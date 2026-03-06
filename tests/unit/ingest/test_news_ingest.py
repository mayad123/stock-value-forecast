"""Tests for Marketaux news ingestion (mocked API)."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


def test_marketaux_missing_key_raises():
    from src.ingest.marketaux import MarketauxError, get_api_key
    with patch.dict(os.environ, {}, clear=False):
        if "MARKETAUX_API_KEY" in os.environ:
            del os.environ["MARKETAUX_API_KEY"]
        with pytest.raises(MarketauxError) as exc:
            get_api_key()
        assert "MARKETAUX_API_KEY" in str(exc.value)


def test_marketaux_fetch_retries_on_429():
    from src.ingest.marketaux import MarketauxError, fetch_news
    import urllib.error
    with patch.dict(os.environ, {"MARKETAUX_API_KEY": "test_key"}):
        with patch("urllib.request.urlopen") as m:
            m.side_effect = urllib.error.HTTPError("", 429, "Rate limit", {}, None)
            with pytest.raises(MarketauxError):
                fetch_news("test_key", symbols=["AAPL"], limit=5)


def test_news_ingest_persists_raw_and_normalized(tmp_path):
    from src.ingest.news import run_ingest_news
    raw_root = tmp_path / "raw"
    raw_root.mkdir(parents=True)
    config = {
        "paths": {"data_raw": str(raw_root)},
        "tickers": {"symbols": ["AAPL"]},
        "time_horizon": {"ingest_start": "2024-01-01", "train_end": "2024-06-30"},
        "news_ingest": {"limit": 10, "max_pages": 1},
    }
    mock_response = {
        "meta": {"found": 100, "returned": 2, "limit": 10, "page": 1},
        "data": [
            {
                "uuid": "art-1",
                "title": "Apple stock rises",
                "published_at": "2024-02-01T12:00:00.000000Z",
                "source": "reuters.com",
                "entities": [{"symbol": "AAPL", "sentiment_score": 0.5, "match_score": 10}],
            },
            {
                "uuid": "art-2",
                "title": "Tech gains",
                "published_at": "2024-02-02T14:00:00.000000Z",
                "source": "bloomberg.com",
                "entities": [{"symbol": "AAPL", "sentiment_score": -0.2, "match_score": 8}],
            },
        ],
    }

    with patch("src.ingest.news.get_api_key", return_value="test_key"):
        with patch("src.ingest.news.fetch_news", return_value=mock_response):
            with patch("src.ingest.news.throttle_wait"):
                version = run_ingest_news(config, data_raw_root=raw_root)
    assert version
    raw_news_dir = raw_root / "news" / "AAPL"
    assert raw_news_dir.exists()
    raw_files = list(raw_news_dir.glob("*.json"))
    assert len(raw_files) == 1
    with open(raw_files[0]) as f:
        saved = json.load(f)
    assert "pages" in saved
    assert len(saved["pages"]) == 1
    assert saved["pages"][0]["data"][0]["title"] == "Apple stock rises"

    normalized_dir = raw_root / "news_normalized" / version
    assert normalized_dir.exists()
    csv_path = normalized_dir / "news.csv"
    assert csv_path.exists()
    content = csv_path.read_text()
    assert "ticker" in content and "publication_timestamp" in content and "sentiment_score" in content

    manifest_path = raw_root / "manifests" / f"news_{version}.json"
    assert manifest_path.exists()
    with open(manifest_path) as f:
        manifest = json.load(f)
    assert manifest["tickers"] == ["AAPL"]
    assert "date_range" in manifest
    assert "api_endpoint" in manifest
    assert "raw_paths" in manifest


def test_normalize_article_extracts_entity_sentiment():
    from src.ingest.news import _normalize_article
    art = {
        "uuid": "u1",
        "title": "Tesla gains",
        "published_at": "2024-01-15T10:00:00Z",
        "source": "cnbc.com",
        "url": "https://cnbc.com/1",
        "entities": [{"symbol": "TSLA", "sentiment_score": 0.7, "match_score": 15}],
    }
    rows = _normalize_article(art, "TSLA")
    assert len(rows) == 1
    assert rows[0]["ticker"] == "TSLA"
    assert rows[0]["sentiment_score"] == 0.7
    assert rows[0]["headline"] == "Tesla gains"
    assert rows[0]["publication_timestamp"] == "2024-01-15T10:00:00Z"
