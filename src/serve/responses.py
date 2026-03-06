"""
Response shaping: build API response models from serve context and data.

Keeps route handlers thin; logic for model_info and prediction_options in one place.
"""

from pathlib import Path
from typing import Dict, List

from src.core.artifacts import resolve_report_path
from src.serve.schemas import ModelInfoResponse, PredictionOptionsResponse
from src.serve.state import ServeContext


def build_model_info(ctx: ServeContext) -> ModelInfoResponse:
    """Build /model_info response from loaded context."""
    run_id = ctx.run_id or ctx.run_record.get("run_id", "unknown")
    dataset_version = ctx.run_record.get("dataset_version", "unknown")
    training_window = (
        ctx.run_record.get("split_boundaries")
        or ctx.run_record.get("config", {}).get("time_horizon")
        or {}
    )
    feature_columns = list(ctx.run_record.get("feature_columns", []))
    tickers_list = sorted(ctx.ticker_to_idx.keys()) if ctx.ticker_to_idx else None
    ticker_fp = ctx.run_record.get("ticker_encoding_fingerprint")
    return ModelInfoResponse(
        model_version=run_id,
        dataset_version=dataset_version,
        num_features=len(feature_columns),
        feature_schema_fingerprint=ctx.schema_fingerprint,
        feature_columns=feature_columns,
        training_window=training_window,
        tickers=tickers_list,
        ticker_encoding_fingerprint=ticker_fp,
    )


def build_prediction_options(ctx: ServeContext) -> PredictionOptionsResponse:
    """Build /prediction_options response from loaded context."""
    tickers_list = sorted(ctx.ticker_to_idx.keys()) if ctx.ticker_to_idx else []
    dates_by_ticker: Dict[str, List[str]] = {}
    df = ctx.features_df
    if df is not None and not df.empty and "ticker" in df.columns and "date" in df.columns:
        for t in tickers_list:
            subset = df[df["ticker"].astype(str).str.upper() == t.upper()]
            if not subset.empty:
                dates = sorted(subset["date"].astype(str).unique().tolist())
                dates_by_ticker[t] = dates
        if not tickers_list and "ticker" in df.columns:
            for t in df["ticker"].astype(str).str.upper().unique().tolist():
                subset = df[df["ticker"].astype(str).str.upper() == t]
                dates_by_ticker[t] = sorted(subset["date"].astype(str).unique().tolist())
            tickers_list = sorted(dates_by_ticker.keys())
    target_cfg = ctx.run_record.get("target") or {}
    horizon_days = int(target_cfg.get("horizon_days", 1))
    horizons = [horizon_days] if horizon_days >= 1 else [1]
    return PredictionOptionsResponse(
        tickers=tickers_list,
        dates_by_ticker=dates_by_ticker,
        horizons=horizons,
    )


def report_path(ctx: ServeContext, filename: str) -> Path:
    """Path to a report file with deploy_artifacts fallback."""
    return resolve_report_path(ctx.reports_path, filename, ctx.repo_root)
