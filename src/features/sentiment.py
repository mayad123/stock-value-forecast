"""
Sentiment aggregation from normalized news.
Aggregates by (ticker, date) with strict prediction-cutoff rule: no article published after
the row date is included (prevents leakage).
"""

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from src.features.split import LeakageError

# Sentiment feature names (used when use_news is True)
SENTIMENT_FEATURE_NAMES = [
    "sentiment_avg",
    "sentiment_count",
    "sentiment_momentum",
]


def load_normalized_news(raw_root: Path, news_dataset_version: str) -> pd.DataFrame:
    """Load normalized news CSV. Expects columns: ticker, publication_timestamp, sentiment_score, etc."""
    path = raw_root / "news_normalized" / news_dataset_version / "news.csv"
    if not path.exists():
        raise FileNotFoundError(f"Normalized news not found: {path}")
    df = pd.read_csv(path)
    if "publication_timestamp" not in df.columns:
        raise ValueError("Normalized news must have publication_timestamp column")
    df["pub_date"] = pd.to_datetime(df["publication_timestamp"].astype(str), errors="coerce").dt.strftime("%Y-%m-%d")
    df = df.dropna(subset=["pub_date"])
    return df


def _safe_mean(series: pd.Series) -> float:
    """Mean of numeric series; 0 if empty or all null."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    return float(s.mean()) if len(s) else 0.0


def build_sentiment_features(
    news_df: pd.DataFrame,
    lookback_days: int = 7,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
) -> pd.DataFrame:
    """
    Aggregate sentiment by (ticker, date) with strict cutoff: for row (ticker, date)
    only articles with pub_date <= date are used (no future-dated articles).
    Produces: sentiment_avg, sentiment_count, sentiment_momentum (change vs prior window).
    """
    if news_df.empty or "sentiment_score" not in news_df.columns:
        out = pd.DataFrame(columns=["ticker", "date"] + SENTIMENT_FEATURE_NAMES)
        return out

    news_df = news_df.copy()
    news_df["sentiment_score"] = pd.to_numeric(news_df["sentiment_score"], errors="coerce").fillna(0.0)
    rows = []

    for ticker, group in news_df.groupby("ticker", sort=True):
        group = group.sort_values("pub_date").drop_duplicates(subset=["article_uuid"], keep="first")
        dates = group["pub_date"].unique()
        if min_date:
            dates = [d for d in dates if d >= min_date]
        if max_date:
            dates = [d for d in dates if d <= max_date]
        for d in sorted(dates):
            # Only articles published on or before d (leakage-safe)
            eligible = group[group["pub_date"] <= d]
            current_window = eligible[eligible["pub_date"] > _date_minus(d, lookback_days)]
            prior_window = eligible[
                (eligible["pub_date"] <= _date_minus(d, lookback_days)) &
                (eligible["pub_date"] > _date_minus(d, 2 * lookback_days))
            ]
            sent_avg = _safe_mean(current_window["sentiment_score"])
            count = len(current_window)
            prior_avg = _safe_mean(prior_window["sentiment_score"])
            momentum = sent_avg - prior_avg
            rows.append({
                "ticker": ticker,
                "date": d,
                "sentiment_avg": round(sent_avg, 10),
                "sentiment_count": count,
                "sentiment_momentum": round(momentum, 10),
            })

    out = pd.DataFrame(rows)
    if out.empty:
        out = pd.DataFrame(columns=["ticker", "date"] + SENTIMENT_FEATURE_NAMES)
    else:
        out = out.sort_values(["ticker", "date"]).reset_index(drop=True)
    return out


def _date_minus(date_str: str, days: int) -> str:
    """Return date_str minus days (naive string YYYY-MM-DD)."""
    d = pd.to_datetime(date_str)
    return (d - pd.Timedelta(days=days)).strftime("%Y-%m-%d")


def validate_sentiment_no_future_leakage(
    sentiment_df: pd.DataFrame,
    price_dates_df: pd.DataFrame,
    ticker_col: str = "ticker",
    date_col: str = "date",
) -> None:
    """
    Ensure no sentiment row uses articles after the prediction cutoff.
    For each (ticker, date) in sentiment used in price_dates_df, we require that
    sentiment was built only from articles with pub_date <= date (enforced by build_sentiment_features).
    This is a sanity check: sentiment_df should only have date = pub_date of articles used;
    we don't store per-article pub_date in the aggregate, so the enforcement is by construction.
    Raises LeakageError if any sentiment date is after the max allowed for that ticker in price_dates_df.
    """
    if sentiment_df.empty or price_dates_df.empty:
        return
    max_by_ticker = price_dates_df.groupby(ticker_col)[date_col].max()
    for _, row in sentiment_df[[ticker_col, date_col]].drop_duplicates().iterrows():
        t, d = row[ticker_col], row[date_col]
        if t not in max_by_ticker.index:
            continue
        if str(d) > str(max_by_ticker[t]):
            raise LeakageError(
                f"Sentiment row (ticker={t}, date={d}) has date after max price date {max_by_ticker[t]}. "
                "No article published after the prediction cutoff may be included in sentiment features."
            )


def resolve_news_version(raw_root: Path, version_hint: str = "latest") -> str:
    """Resolve news dataset version from manifests. version_hint can be 'latest' or a news_{version}.json stem."""
    manifests_dir = raw_root / "manifests"
    if not manifests_dir.exists():
        raise FileNotFoundError(f"No manifests dir: {manifests_dir}")
    if version_hint != "latest":
        manifest_path = manifests_dir / f"news_{version_hint}.json"
        if manifest_path.exists():
            return version_hint
        raise FileNotFoundError(f"News dataset version not found: {version_hint}")
    news_manifests = sorted(manifests_dir.glob("news_*.json"))
    if not news_manifests:
        raise FileNotFoundError(f"No news manifests in {manifests_dir}")
    return news_manifests[-1].stem.replace("news_", "", 1)
