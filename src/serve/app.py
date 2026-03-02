"""
Production-style FastAPI service: load model at startup, serve /health, /predict, /model_info.
Uses stored trained artifact only; no re-training.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException

from src.serve.schemas import ModelInfoResponse, PredictRequest, PredictResponse

# Resolved at startup (paths relative to repo root)
_repo_root: Path = Path(__file__).resolve().parents[2]

# Load .env from repo root so MODEL_RUN_ID etc. are available when run via uvicorn
try:
    from dotenv import load_dotenv
    load_dotenv(_repo_root / ".env")
except ImportError:
    pass
_model = None
_run_record: Optional[Dict[str, Any]] = None
_run_id: Optional[str] = None
_features_df: Optional[pd.DataFrame] = None
_models_path: Path = _repo_root / "models"
_processed_path: Path = _repo_root / "data" / "processed"


def _resolve_run_dir() -> Path:
    """Resolve model run directory: env MODEL_RUN_ID, or latest in models/."""
    import os
    run_id = os.environ.get("MODEL_RUN_ID", "").strip()
    def _has_model(d: Path) -> bool:
        return (d / "model.keras").exists() or (d / "saved_model").exists()

    if run_id:
        d = _models_path / run_id
        if d.is_dir() and _has_model(d):
            return d
        raise FileNotFoundError(f"MODEL_RUN_ID run not found: {run_id}")
    if not _models_path.exists():
        raise FileNotFoundError(f"Models dir not found: {_models_path}")
    candidates = sorted(
        d for d in _models_path.iterdir()
        if d.is_dir() and _has_model(d) and (d / "run_record.json").exists()
    )
    if not candidates:
        raise FileNotFoundError(f"No trained model found in {_models_path}")
    return candidates[-1]


def _load_artifacts() -> None:
    global _model, _run_record, _run_id, _features_df, _models_path, _processed_path
    import os
    if os.environ.get("SERVE_MODELS_PATH"):
        _models_path = Path(os.environ["SERVE_MODELS_PATH"])
    if os.environ.get("SERVE_PROCESSED_PATH"):
        _processed_path = Path(os.environ["SERVE_PROCESSED_PATH"])
    run_dir = _resolve_run_dir()
    _run_id = run_dir.name
    from src.train.load import load_trained_model
    _model, _run_record = load_trained_model(run_dir)
    _run_record.setdefault("run_id", _run_id)
    dataset_version = _run_record.get("dataset_version", "")
    features_path = _processed_path / dataset_version / "features.csv"
    if features_path.exists():
        _features_df = pd.read_csv(features_path)
        _features_df["date"] = _features_df["date"].astype(str)
    else:
        _features_df = pd.DataFrame()


def _lookup_features(ticker: str, as_of: str) -> Optional[pd.Series]:
    """Return feature row for (ticker, date <= as_of), latest date first."""
    if _features_df is None or _features_df.empty:
        return None
    subset = _features_df[
        (_features_df["ticker"].astype(str).str.upper() == ticker.upper()) &
        (_features_df["date"].astype(str) <= as_of)
    ]
    if subset.empty:
        return None
    subset = subset.sort_values("date", ascending=False)
    return subset.iloc[0]


def _predict_one(row: pd.Series) -> tuple:
    """Run model on one feature row; return (prediction, confidence)."""
    import numpy as np
    feature_cols = _run_record.get("feature_columns", [])
    scaler = _run_record.get("scaler", {})
    mean = np.array(scaler.get("mean", [0.0] * len(feature_cols)), dtype=np.float32)
    scale = np.array(scaler.get("scale", [1.0] * len(feature_cols)), dtype=np.float32)
    X = np.array([[row.get(c, 0) for c in feature_cols]], dtype=np.float32)
    X_n = (X - mean) / scale
    pred = _model.predict(X_n, verbose=0)
    score = float(pred.flatten()[0])
    confidence = 0.5 + 0.5 * (1.0 - min(1.0, abs(score)))
    return score, confidence


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model and optional features at startup."""
    try:
        _load_artifacts()
        yield
    finally:
        pass


app = FastAPI(title="Stock Trend Prediction API", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    """Health check."""
    return {"status": "ok"}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest) -> PredictResponse:
    """Return prediction and confidence for ticker at as_of date (uses stored artifact)."""
    if _model is None or _run_record is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    ticker = req.ticker.strip().upper()
    as_of = req.as_of.strip()
    horizon = req.horizon or 1
    row = _lookup_features(ticker, as_of)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"No feature row for ticker={ticker} with date<={as_of}. Ensure processed data exists."
        )
    prediction, confidence = _predict_one(row)
    used_date = str(row.get("date", as_of))
    return PredictResponse(
        prediction=round(prediction, 6),
        confidence=round(confidence, 4),
        ticker=ticker,
        as_of=used_date,
        horizon=horizon,
    )


@app.get("/model_info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    """Return model version, training window, dataset version."""
    if _run_record is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    run_id = _run_id or _run_record.get("run_id", "unknown")
    dataset_version = _run_record.get("dataset_version", "unknown")
    training_window = _run_record.get("split_boundaries") or _run_record.get("config", {}).get("time_horizon") or {}
    feature_columns = _run_record.get("feature_columns", [])
    return ModelInfoResponse(
        model_version=run_id,
        training_window=training_window,
        dataset_version=dataset_version,
        feature_columns=feature_columns,
    )
