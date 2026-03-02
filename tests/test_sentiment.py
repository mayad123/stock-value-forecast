"""Tests for sentiment aggregation and leakage rule."""

import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.features.sentiment import (  # noqa: E402
    SENTIMENT_FEATURE_NAMES,
    build_sentiment_features,
    load_normalized_news,
    resolve_news_version,
    validate_sentiment_no_future_leakage,
)
from src.features.split import LeakageError  # noqa: E402


def test_build_sentiment_features_empty():
    out = build_sentiment_features(pd.DataFrame(), lookback_days=7)
    assert list(out.columns) == ["ticker", "date"] + SENTIMENT_FEATURE_NAMES
    assert len(out) == 0


def test_build_sentiment_features_daily_bucket_no_future():
    df = pd.DataFrame([
        {"ticker": "AAPL", "publication_timestamp": "2024-01-10T12:00:00Z", "sentiment_score": 0.5, "article_uuid": "a1"},
        {"ticker": "AAPL", "publication_timestamp": "2024-01-11T09:00:00Z", "sentiment_score": -0.2, "article_uuid": "a2"},
        {"ticker": "AAPL", "publication_timestamp": "2024-01-11T14:00:00Z", "sentiment_score": 0.1, "article_uuid": "a3"},
    ])
    df["pub_date"] = pd.to_datetime(df["publication_timestamp"].astype(str), errors="coerce").dt.strftime("%Y-%m-%d")
    out = build_sentiment_features(df, lookback_days=7)
    assert not out.empty
    assert "sentiment_avg" in out.columns
    assert "sentiment_count" in out.columns
    assert "sentiment_momentum" in out.columns
    aapl = out[out["ticker"] == "AAPL"]
    assert len(aapl) >= 1
    row_11 = aapl[aapl["date"] == "2024-01-11"].iloc[0]
    assert row_11["sentiment_count"] >= 2
    assert -1 <= row_11["sentiment_avg"] <= 1


def test_validate_sentiment_no_future_leakage_raises():
    sentiment_df = pd.DataFrame([
        {"ticker": "X", "date": "2024-02-01"},
    ])
    price_df = pd.DataFrame([
        {"ticker": "X", "date": "2024-01-15"},
    ])
    with pytest.raises(LeakageError):
        validate_sentiment_no_future_leakage(sentiment_df, price_df)


def test_validate_sentiment_no_future_leakage_passes():
    sentiment_df = pd.DataFrame([
        {"ticker": "X", "date": "2024-01-15"},
    ])
    price_df = pd.DataFrame([
        {"ticker": "X", "date": "2024-01-15"},
    ])
    validate_sentiment_no_future_leakage(sentiment_df, price_df)


def test_resolve_news_version_latest(tmp_path):
    (tmp_path / "manifests").mkdir(parents=True)
    (tmp_path / "manifests" / "news_2024-01-01T00-00-00.json").write_text("{}")
    (tmp_path / "manifests" / "news_2024-02-01T00-00-00.json").write_text("{}")
    v = resolve_news_version(tmp_path, "latest")
    assert v == "2024-02-01T00-00-00"


def test_load_normalized_news(tmp_path):
    version = "v1"
    (tmp_path / "news_normalized" / version).mkdir(parents=True)
    csv = "ticker,publication_timestamp,headline,source,sentiment_score,match_score,relevance_score,article_uuid,url\n"
    csv += "AAPL,2024-01-10T12:00:00Z,Headline,src.com,0.5,10,,u1,http://u1\n"
    (tmp_path / "news_normalized" / version / "news.csv").write_text(csv)
    df = load_normalized_news(tmp_path, version)
    assert len(df) == 1
    assert "pub_date" in df.columns
    assert df["pub_date"].iloc[0] == "2024-01-10"
