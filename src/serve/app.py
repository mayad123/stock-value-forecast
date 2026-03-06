"""
Production-style FastAPI service: load model at startup, serve /health, /predict, /model_info, etc.

Routing and request/response wiring only; model loading, feature lookup, prediction,
and response shaping live in serve/loader, feature_lookup, predictor, responses.
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

from src.core.paths import repo_root
from src.serve.feature_lookup import lookup_features
from src.serve.loader import load_artifacts_from_env
from src.serve.predictor import predict_one, row_to_feature_vector, unknown_ticker_detail, validate_feature_input
from src.serve.responses import build_model_info, build_prediction_options, report_path
from src.serve.schemas import (
    FeatureImportanceResponse,
    ModelInfoResponse,
    PredictRequest,
    PredictResponse,
    PredictionOptionsResponse,
)
from src.serve.state import ServeContext

# Load .env from repo root so MODEL_RUN_ID etc. are available when run via uvicorn
_repo_root: Path = repo_root()
try:
    from dotenv import load_dotenv
    load_dotenv(_repo_root / ".env")
except ImportError:
    pass

_ctx: Optional[ServeContext] = None


def _get_ctx() -> ServeContext:
    if _ctx is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return _ctx


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model and artifacts at startup; store in global context."""
    global _ctx
    try:
        _ctx = load_artifacts_from_env(_repo_root)
        yield
    finally:
        _ctx = None


app = FastAPI(title="Stock Trend Prediction API", version="0.1.0", lifespan=lifespan)


# ----- Health -----


@app.get("/health")
def health() -> dict:
    """Health check."""
    return {"status": "ok"}


# ----- Prediction -----


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    """
    Return prediction and confidence. Inputs validated against trained feature schema.
    Either omit features (lookup from processed data by ticker/as_of) or provide features dict.
    """
    ctx = _get_ctx()
    ticker = req.ticker.strip().upper()
    as_of = req.as_of.strip()
    horizon = req.horizon or 1

    if req.features is not None:
        validate_feature_input(ctx, req.features, strict=True)
        feature_vector = row_to_feature_vector(ctx, req.features)
        used_date = as_of
    else:
        if ctx.ticker_to_idx and ticker not in ctx.ticker_to_idx:
            raise HTTPException(status_code=400, detail=unknown_ticker_detail(ctx, ticker))
        row = lookup_features(ctx, ticker, as_of)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"No feature row for ticker={ticker} with date<={as_of}. Ensure processed data exists.",
            )
        validate_feature_input(ctx, row, strict=False)
        feature_vector = row_to_feature_vector(ctx, row)
        used_date = str(row.get("date", as_of))

    prediction, confidence = predict_one(ctx, feature_vector)
    return PredictResponse(
        prediction=round(prediction, 6),
        confidence=round(confidence, 4),
        ticker=ticker,
        as_of=used_date,
        horizon=horizon,
        model_version=ctx.run_id,
    )


@app.get("/prediction_options", response_model=PredictionOptionsResponse)
def prediction_options() -> PredictionOptionsResponse:
    """Valid (ticker, date, horizon) choices for prediction UIs."""
    ctx = _get_ctx()
    return build_prediction_options(ctx)


@app.get("/model_info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    """Model version, dataset version, feature count, schema fingerprint."""
    ctx = _get_ctx()
    return build_model_info(ctx)


# ----- Read-only data (reports, prices) -----


@app.get("/metrics")
def get_metrics() -> Dict[str, Any]:
    """Contents of reports/latest_metrics.json."""
    ctx = _get_ctx()
    path = report_path(ctx, "latest_metrics.json")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Metrics file not found. Run a backtest to generate it.")
    with open(path) as f:
        return json.load(f)


@app.get("/predictions")
def get_predictions(
    ticker: Optional[str] = Query(None, description="Filter by ticker (e.g. AAPL)"),
    model_name: Optional[str] = Query(None, description="Filter by model name"),
) -> List[Dict[str, Any]]:
    """Contents of reports/latest_predictions.csv as JSON. Optional filters: ticker, model_name."""
    ctx = _get_ctx()
    path = report_path(ctx, "latest_predictions.csv")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Predictions file not found. Run a backtest to generate it.")
    df = pd.read_csv(path)
    if df.empty:
        return []
    if ticker is not None and ticker.strip():
        t = ticker.strip().upper()
        if "ticker" in df.columns:
            df = df[df["ticker"].astype(str).str.upper() == t]
    if model_name is not None and model_name.strip():
        m = model_name.strip()
        if "model_name" in df.columns:
            df = df[df["model_name"].astype(str) == m]
    out = df.to_dict(orient="records")
    for row in out:
        for k, v in list(row.items()):
            if isinstance(v, float) and pd.isna(v):
                row[k] = None
            elif isinstance(v, pd.Timestamp):
                row[k] = str(v)
    return out


@app.get("/feature_importance", response_model=FeatureImportanceResponse)
def get_feature_importance() -> FeatureImportanceResponse:
    """Contents of reports/latest_feature_importance.json."""
    ctx = _get_ctx()
    path = report_path(ctx, "latest_feature_importance.json")
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="Feature importance not found. Run `python run.py feature-importance` to generate it.",
        )
    with open(path) as f:
        data = json.load(f)
    return FeatureImportanceResponse(**data)


@app.get("/prices")
def get_prices(
    ticker: str = Query(..., description="Ticker symbol (e.g. AAPL)"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD (inclusive)"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD (inclusive)"),
) -> List[Dict[str, Any]]:
    """Historical price series from offline demo dataset. Date-sorted. Read-only."""
    ctx = _get_ctx()
    if not ticker or not ticker.strip():
        raise HTTPException(status_code=400, detail="ticker is required")
    sym = ticker.strip().upper()
    path = ctx.sample_prices_path / f"{sym}.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No price data for ticker={sym}")
    df = pd.read_csv(path)
    if df.empty:
        return []
    if "date" not in df.columns:
        raise HTTPException(status_code=500, detail="Price file has no date column")
    df["date"] = df["date"].astype(str)
    df = df.sort_values("date").reset_index(drop=True)
    if start_date is not None and start_date.strip():
        df = df[df["date"] >= start_date.strip()]
    if end_date is not None and end_date.strip():
        df = df[df["date"] <= end_date.strip()]
    out = df.to_dict(orient="records")
    for row in out:
        for k, v in list(row.items()):
            if isinstance(v, pd.Timestamp):
                row[k] = str(v)
            elif isinstance(v, float) and pd.isna(v):
                row[k] = None
    return out
