"""
Deterministic price-only feature generation.
Same raw input + same config => identical processed output (idempotent).
Time-series split and leakage constraints enforced; pipeline fails loudly on violation.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.features.split import (
    apply_split,
    get_split_boundaries,
    validate_boundaries,
    validate_prediction_cutoff_per_ticker,
    validate_time_ordering_processed,
    validate_time_ordering_raw,
)
from src.features.sentiment import (
    SENTIMENT_FEATURE_NAMES,
    build_sentiment_features,
    load_normalized_news,
    resolve_news_version,
    validate_sentiment_no_future_leakage,
)

# Fixed column order for determinism
ID_COLS = ["ticker", "date"]
FEATURE_NAMES = [
    "return_1d",
    "return_5d",
    "return_21d",
    "volatility_5d",
    "volatility_21d",
    "range_hl",
    "volume_pct_1d",
]
TARGET_NAME = "target_forward_return"


def _get_feature_definitions(include_news: bool = False) -> List[Dict[str, str]]:
    """Stable list of feature names and descriptions for the manifest."""
    out = [
        {"name": "return_1d", "description": "1-day simple return on adjusted close"},
        {"name": "return_5d", "description": "5-day simple return on adjusted close"},
        {"name": "return_21d", "description": "21-day simple return on adjusted close"},
        {"name": "volatility_5d", "description": "Rolling 5-day std of 1-day returns"},
        {"name": "volatility_21d", "description": "Rolling 21-day std of 1-day returns"},
        {"name": "range_hl", "description": "(high - low) / close"},
        {"name": "volume_pct_1d", "description": "1-day pct change in volume"},
    ]
    if include_news:
        out.extend([
            {"name": "sentiment_avg", "description": "Average news sentiment in lookback window (daily bucket)"},
            {"name": "sentiment_count", "description": "Count of articles in sentiment window"},
            {"name": "sentiment_momentum", "description": "Change in avg sentiment vs prior window"},
        ])
    out.append({"name": TARGET_NAME, "description": "Forward N-day return (label)"})
    return out


def get_feature_names(use_news: bool = False) -> List[str]:
    """Return feature column list (price-only or price + sentiment)."""
    if use_news:
        return FEATURE_NAMES + SENTIMENT_FEATURE_NAMES
    return list(FEATURE_NAMES)


def load_raw_normalized(raw_root: Path, raw_dataset_version: str) -> pd.DataFrame:
    """
    Load normalized prices for a raw dataset version.
    Uses manifest's normalized_paths: either ticker-level history files (incremental store)
    or legacy single CSV at prices_normalized/{version}/prices.csv.
    Returns DataFrame sorted by (ticker, date). Validates time ordering (fails loudly on violation).
    """
    manifest_path = raw_root / "manifests" / f"{raw_dataset_version}.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path) as f:
        manifest = json.load(f)
    normalized_paths = manifest.get("normalized_paths") or []

    if not normalized_paths:
        # Legacy: single versioned CSV
        csv_path = raw_root / "prices_normalized" / raw_dataset_version / "prices.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Normalized prices not found: {csv_path}")
        paths_to_load = [csv_path]
    else:
        paths_to_load = [raw_root / p for p in normalized_paths]

    dfs = []
    for p in paths_to_load:
        if not p.exists():
            raise FileNotFoundError(f"Normalized price file not found: {p}")
        dfs.append(pd.read_csv(p))
    df = pd.concat(dfs, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    validate_time_ordering_raw(df)
    return df


def build_features(
    df: pd.DataFrame,
    lookback_days: int = 21,
    forward_return_days: int = 1,
    date_range: Optional[Dict[str, str]] = None,
) -> pd.DataFrame:
    """
    Compute price-derived features and target. Fully deterministic.
    - Features: returns (1d, 5d, 21d), volatilities (5d, 21d), range_hl, volume_pct_1d
    - Target: forward_return_days simple return on adjusted_close
    Rows with NaN target (end of series) are dropped. Output sorted by (ticker, date).
    """
    df = df.sort_values(["ticker", "date"]).reset_index(drop=True)
    out_rows = []

    for ticker, group in df.groupby("ticker", sort=True):
        group = group.sort_values("date").reset_index(drop=True)
        adj = group["adjusted_close"].astype(float)
        high = group["high"].astype(float)
        low = group["low"].astype(float)
        close = group["close"].astype(float)
        vol = group["volume"].fillna(0).astype(float)

        # Returns (log return for stability)
        return_1d = adj.pct_change(1)
        return_5d = adj.pct_change(5)
        return_21d = adj.pct_change(lookback_days)

        # Volatility: rolling std of 1d returns
        volatility_5d = return_1d.rolling(5, min_periods=5).std()
        volatility_21d = return_1d.rolling(lookback_days, min_periods=lookback_days).std()

        # Range and volume
        range_hl = (high - low) / close.replace(0, float("nan"))
        volume_pct_1d = vol.pct_change(1).fillna(0)

        # Target: forward N-day return
        target = adj.shift(-forward_return_days) / adj - 1.0

        for i in range(len(group)):
            if i < lookback_days:
                continue
            if pd.isna(target.iloc[i]):
                continue
            row = {
                "ticker": ticker,
                "date": group["date"].iloc[i],
                "return_1d": round(float(return_1d.iloc[i]), 10) if not pd.isna(return_1d.iloc[i]) else None,
                "return_5d": round(float(return_5d.iloc[i]), 10) if not pd.isna(return_5d.iloc[i]) else None,
                "return_21d": round(float(return_21d.iloc[i]), 10) if not pd.isna(return_21d.iloc[i]) else None,
                "volatility_5d": round(float(volatility_5d.iloc[i]), 10) if not pd.isna(volatility_5d.iloc[i]) else None,
                "volatility_21d": round(float(volatility_21d.iloc[i]), 10) if not pd.isna(volatility_21d.iloc[i]) else None,
                "range_hl": round(float(range_hl.iloc[i]), 10) if not pd.isna(range_hl.iloc[i]) else None,
                "volume_pct_1d": round(float(volume_pct_1d.iloc[i]), 10),
                "target_forward_return": round(float(target.iloc[i]), 10),
            }
            if date_range:
                if date_range.get("min") and row["date"] < date_range["min"]:
                    continue
                if date_range.get("max") and row["date"] > date_range["max"]:
                    continue
            out_rows.append(row)

    out = pd.DataFrame(out_rows)
    if out.empty:
        return out
    # Deterministic column order and sort
    cols = ID_COLS + FEATURE_NAMES + [TARGET_NAME]
    out = out[[c for c in cols if c in out.columns]]
    out = out.sort_values(["ticker", "date"]).reset_index(drop=True)
    validate_time_ordering_processed(out)
    return out


def resolve_raw_version(raw_root: Path, version_hint: str = "latest") -> str:
    """Resolve raw dataset version: 'latest' -> most recent price manifest, else use hint."""
    manifests_dir = raw_root / "manifests"
    if not manifests_dir.exists():
        raise FileNotFoundError(f"No manifests dir: {manifests_dir}")

    if version_hint != "latest":
        manifest_path = manifests_dir / f"{version_hint}.json"
        if manifest_path.exists() and not manifest_path.name.startswith("news_"):
            return version_hint
        raise FileNotFoundError(f"Raw dataset version not found: {version_hint}")

    # Only price manifests (exclude news_*.json)
    manifests = sorted(m for m in manifests_dir.glob("*.json") if not m.name.startswith("news_"))
    if not manifests:
        raise FileNotFoundError(f"No price manifests in {manifests_dir}")
    return manifests[-1].stem


def run_build_features(
    config: Dict[str, Any],
    raw_root: Optional[Path] = None,
    processed_root: Optional[Path] = None,
    log: Optional[Any] = None,
) -> str:
    """
    Load raw normalized prices, build features, write processed dataset and feature manifest.
    Returns processed dataset version (same as raw_dataset_version for 1:1 link).
    """
    if log is None:
        def log(msg: str) -> None:
            print(f"[BUILD-FEATURES] {msg}")

    paths_cfg = config.get("paths", {})
    repo_root = Path(__file__).resolve().parents[2]
    raw_root = raw_root or (repo_root / paths_cfg.get("data_raw", "data/raw"))
    if not raw_root.is_absolute():
        raw_root = repo_root / raw_root

    processed_path = processed_root or (repo_root / paths_cfg.get("data_processed", "data/processed"))
    if not processed_path.is_absolute():
        processed_path = repo_root / processed_path

    raw_version_hint = config.get("feature_build", {}).get("raw_dataset_version", "latest")
    raw_dataset_version = resolve_raw_version(raw_root, raw_version_hint)
    log(f"Raw dataset version: {raw_dataset_version}")

    df = load_raw_normalized(raw_root, raw_dataset_version)
    log(f"Loaded {len(df)} rows from normalized prices")

    fw = config.get("feature_windows", {})
    lookback = int(fw.get("lookback_days", 21))
    forward_days = int(fw.get("forward_return_days", 1))
    time_horizon = config.get("time_horizon", {})
    date_range = None
    if time_horizon.get("ingest_start"):
        date_range = {"min": time_horizon["ingest_start"]}
        # Do not set max here; train/val/test split is applied after feature build

    out_df = build_features(df, lookback_days=lookback, forward_return_days=forward_days, date_range=date_range)
    use_news = bool(config.get("use_news"))
    feature_names = get_feature_names(use_news)
    log(f"Built {len(out_df)} rows with {len(feature_names)} features + target")

    if use_news:
        news_version_hint = config.get("feature_build", {}).get("news_dataset_version", "latest")
        try:
            news_dataset_version = resolve_news_version(raw_root, news_version_hint)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"use_news is True but news data not found: {e}. Run ingest with use_news: true first."
            ) from e
        news_df = load_normalized_news(raw_root, news_dataset_version)
        news_lookback = int(fw.get("news_lookback_days", 7))
        sentiment_df = build_sentiment_features(
            news_df,
            lookback_days=news_lookback,
            min_date=date_range.get("min") if date_range else None,
            max_date=None,
        )
        validate_sentiment_no_future_leakage(sentiment_df, out_df)
        out_df = out_df.merge(
            sentiment_df,
            on=["ticker", "date"],
            how="left",
        )
        for c in SENTIMENT_FEATURE_NAMES:
            if c not in out_df.columns:
                out_df[c] = 0.0
            out_df[c] = out_df[c].fillna(0.0)
        log(f"Merged sentiment (news version {news_dataset_version}, lookback {news_lookback}d)")

    # Time-series split and leakage enforcement
    boundaries = get_split_boundaries(config)
    validate_boundaries(boundaries)
    out_df, split_counts = apply_split(out_df, boundaries)
    validate_prediction_cutoff_per_ticker(df, out_df)
    log(f"Split: train={split_counts['train']}, val={split_counts['val']}, test={split_counts['test']}")

    out_dir = processed_path / raw_dataset_version
    out_dir.mkdir(parents=True, exist_ok=True)

    # Deterministic write: fixed column order (split column first after ids for clarity)
    cols = [c for c in (ID_COLS + ["split"] + feature_names + [TARGET_NAME]) if c in out_df.columns]
    out_df = out_df[cols]
    features_csv = out_dir / "features.csv"
    out_df.to_csv(features_csv, index=False, float_format="%.10f")
    log(f"Wrote {features_csv}")

    raw_manifest_path = raw_root / "manifests" / f"{raw_dataset_version}.json"
    feature_manifest = {
        "raw_dataset_version": raw_dataset_version,
        "raw_manifest_path": str(raw_manifest_path.relative_to(raw_root)) if raw_manifest_path.exists() else None,
        "feature_definitions": _get_feature_definitions(include_news=use_news),
        "feature_windows": {"lookback_days": lookback, "forward_return_days": forward_days, "news_lookback_days": fw.get("news_lookback_days", 7)},
        "split_boundaries": boundaries,
        "split_counts": split_counts,
        "leakage_rule": "No data later than the prediction cutoff (row date) is used in feature generation; only past and same-day data. No article published after prediction cutoff is included in sentiment features.",
        "processed_paths": [str(features_csv.relative_to(processed_path))],
        "row_count": int(len(out_df)),
        "id_columns": ID_COLS,
        "feature_columns": feature_names,
        "target_column": TARGET_NAME,
    }
    manifest_path = out_dir / "feature_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(feature_manifest, f, indent=2)
    log(f"Wrote {manifest_path}")

    return raw_dataset_version
