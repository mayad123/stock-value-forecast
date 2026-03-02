"""
Production-style FastAPI service: load model at startup, serve /health, /predict, /model_info.
Validates inference inputs against the trained feature schema to prevent train/serve skew.
"""

import hashlib
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

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
_reports_path: Path = _repo_root / "reports"
_sample_prices_path: Path = _repo_root / "data" / "sample" / "prices_normalized"


def _resolve_data_paths() -> None:
    """Apply env overrides for reports and sample prices (e.g. in tests or cloud)."""
    global _reports_path, _sample_prices_path
    import os
    if os.environ.get("SERVE_REPORTS_PATH"):
        _reports_path = Path(os.environ["SERVE_REPORTS_PATH"]).resolve()
    if os.environ.get("SERVE_SAMPLE_PRICES_PATH"):
        _sample_prices_path = Path(os.environ["SERVE_SAMPLE_PRICES_PATH"]).resolve()

# Schema contract (set at startup from run_record)
_feature_columns: List[str] = []
_ticker_columns: List[str] = []
_ticker_to_idx: Dict[str, int] = {}
_expected_dim: int = 0
_schema_fingerprint: str = ""


def _compute_schema_fingerprint(feature_columns: List[str]) -> str:
    """Stable identifier from feature column names and order."""
    blob = json.dumps(feature_columns, sort_keys=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


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
    global _feature_columns, _ticker_columns, _ticker_to_idx, _expected_dim, _schema_fingerprint
    import os
    _resolve_data_paths()
    if os.environ.get("SERVE_MODELS_PATH"):
        _models_path = Path(os.environ["SERVE_MODELS_PATH"])
    elif not (_models_path.exists() and any(
        d.is_dir() and ((d / "model.keras").exists() or (d / "saved_model").exists()) and (d / "run_record.json").exists()
        for d in _models_path.iterdir()
    )):
        # Fallback for cloud deploy: use committed deploy_artifacts when models/ is missing/empty
        _fallback = _repo_root / "deploy_artifacts" / "models"
        if _fallback.exists() and any(
            d.is_dir() and ((d / "model.keras").exists() or (d / "saved_model").exists()) and (d / "run_record.json").exists()
            for d in _fallback.iterdir()
        ):
            _models_path = _fallback
    if os.environ.get("SERVE_PROCESSED_PATH"):
        _processed_path = Path(os.environ["SERVE_PROCESSED_PATH"])
    elif not _processed_path.exists() and (_repo_root / "deploy_artifacts" / "processed").exists():
        _processed_path = _repo_root / "deploy_artifacts" / "processed"
    run_dir = _resolve_run_dir()
    _run_id = run_dir.name
    from src.train.load import load_trained_model
    _model, _run_record = load_trained_model(run_dir)
    _run_record.setdefault("run_id", _run_id)
    _feature_columns = list(_run_record.get("feature_columns", []))
    _ticker_columns = list(_run_record.get("ticker_columns", []))
    _ticker_to_idx = dict(_run_record.get("ticker_to_idx", {}))
    _expected_dim = len(_feature_columns)
    _schema_fingerprint = _compute_schema_fingerprint(_feature_columns)
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


def _unknown_ticker_detail(requested: str) -> Dict[str, Any]:
    """Structured 400 body for unknown ticker: list of known tickers and count."""
    known = sorted(_ticker_to_idx.keys())
    return {
        "error": "unknown_ticker",
        "message": f"Ticker '{requested}' is not in the trained ticker set.",
        "requested_ticker": requested,
        "known_tickers": known,
        "count": len(known),
    }


def _validate_feature_input(received: Dict[str, Any], strict: bool = True) -> None:
    """
    Validate received keys against trained feature_columns.
    strict=True: exact match (no missing, no extra) for client-provided features.
    strict=False: allow ticker + price columns only; ticker one-hot will be injected. Ticker must be in run record.
    """
    expected_set = set(_feature_columns)
    received_set = set(received.keys()) if received else set()
    missing = expected_set - received_set
    ticker_set = set(_ticker_columns)
    if not strict and ticker_set and "ticker" in received_set:
        missing = missing - ticker_set
        ticker_val = str(received.get("ticker", "")).strip().upper()
        if ticker_val and ticker_val not in _ticker_to_idx:
            raise HTTPException(status_code=400, detail=_unknown_ticker_detail(ticker_val))
    extra = received_set - expected_set
    if missing:
        detail = (
            "Feature schema mismatch: expected vs received. "
            f"Expected {sorted(_feature_columns)}; received {sorted(received_set)}. "
            f"Missing: {sorted(missing)}. Extra: {sorted(extra)}."
        )
        raise HTTPException(status_code=400, detail=detail)
    if strict and extra:
        detail = (
            "Feature schema mismatch: expected vs received. "
            f"Expected {sorted(_feature_columns)}; received {sorted(received_set)}. "
            f"Missing: {sorted(missing)}. Extra: {sorted(extra)}."
        )
        raise HTTPException(status_code=400, detail=detail)


def _row_to_feature_vector(row: Dict[str, Any]) -> List[float]:
    """Build feature vector in trained order; ticker one-hot from row['ticker'] when column not in row."""
    out: List[float] = []
    ticker_val = str(row.get("ticker", "")).strip().upper() if row.get("ticker") is not None else ""
    for c in _feature_columns:
        if c in _ticker_columns and _ticker_to_idx and (c not in row or row.get(c) is None):
            idx = _ticker_columns.index(c)
            out.append(1.0 if _ticker_to_idx.get(ticker_val) == idx else 0.0)
        else:
            out.append(float(row.get(c, 0)))
    return out


def _predict_one(feature_vector: List[float]) -> tuple:
    """Run model on one feature vector (in trained order); return (prediction, confidence)."""
    import numpy as np
    scaler = _run_record.get("scaler", {})
    mean = np.array(scaler.get("mean", [0.0] * _expected_dim), dtype=np.float32)
    scale = np.array(scaler.get("scale", [1.0] * _expected_dim), dtype=np.float32)
    X = np.array([feature_vector], dtype=np.float32)
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
    """
    Return prediction and confidence. Inputs are validated against the trained feature schema.
    Either omit features (lookup from processed data by ticker/as_of) or provide features
    as a named mapping; it must match trained feature_columns exactly (re-ordered internally).
    """
    if _model is None or _run_record is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    ticker = req.ticker.strip().upper()
    as_of = req.as_of.strip()
    horizon = req.horizon or 1

    if req.features is not None:
        _validate_feature_input(req.features)
        feature_vector = _row_to_feature_vector(req.features)
        used_date = as_of
    else:
        if _ticker_to_idx and ticker not in _ticker_to_idx:
            raise HTTPException(status_code=400, detail=_unknown_ticker_detail(ticker))
        row = _lookup_features(ticker, as_of)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"No feature row for ticker={ticker} with date<={as_of}. Ensure processed data exists.",
            )
        row_dict = row.to_dict() if hasattr(row, "to_dict") else dict(row)
        _validate_feature_input(row_dict, strict=False)
        feature_vector = _row_to_feature_vector(row_dict)
        used_date = str(row.get("date", as_of))

    prediction, confidence = _predict_one(feature_vector)
    return PredictResponse(
        prediction=round(prediction, 6),
        confidence=round(confidence, 4),
        ticker=ticker,
        as_of=used_date,
        horizon=horizon,
        model_version=_run_id,
    )


@app.get("/model_info", response_model=ModelInfoResponse)
def model_info() -> ModelInfoResponse:
    """Return model version, dataset version, number of features, feature schema fingerprint."""
    if _run_record is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    run_id = _run_id or _run_record.get("run_id", "unknown")
    dataset_version = _run_record.get("dataset_version", "unknown")
    training_window = _run_record.get("split_boundaries") or _run_record.get("config", {}).get("time_horizon") or {}
    feature_columns = list(_run_record.get("feature_columns", []))
    tickers_list = sorted(_ticker_to_idx.keys()) if _ticker_to_idx else None
    ticker_fp = _run_record.get("ticker_encoding_fingerprint")
    return ModelInfoResponse(
        model_version=run_id,
        dataset_version=dataset_version,
        num_features=len(feature_columns),
        feature_schema_fingerprint=_schema_fingerprint,
        feature_columns=feature_columns,
        training_window=training_window,
        tickers=tickers_list,
        ticker_encoding_fingerprint=ticker_fp,
    )


# ----- Read-only data endpoints (no external APIs, no ingestion/training) -----


@app.get("/metrics")
def get_metrics() -> Dict[str, Any]:
    """Return contents of reports/latest_metrics.json. Read-only."""
    path = _reports_path / "latest_metrics.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Metrics file not found. Run a backtest to generate it.")
    with open(path) as f:
        return json.load(f)


@app.get("/predictions")
def get_predictions(
    ticker: Optional[str] = Query(None, description="Filter by ticker (e.g. AAPL)"),
    model_name: Optional[str] = Query(None, description="Filter by model name"),
) -> List[Dict[str, Any]]:
    """Return contents of reports/latest_predictions.csv as JSON. Optional filters: ticker, model_name. Read-only."""
    path = _reports_path / "latest_predictions.csv"
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
            elif isinstance(v, (pd.Timestamp,)):
                row[k] = str(v)
    return out


@app.get("/prices")
def get_prices(
    ticker: str = Query(..., description="Ticker symbol (e.g. AAPL)"),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD (inclusive)"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD (inclusive)"),
) -> List[Dict[str, Any]]:
    """Return historical price series from offline demo dataset. Date-sorted. Read-only, no external APIs."""
    if not ticker or not ticker.strip():
        raise HTTPException(status_code=400, detail="ticker is required")
    sym = ticker.strip().upper()
    path = _sample_prices_path / f"{sym}.csv"
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
