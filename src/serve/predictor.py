"""
Prediction logic: feature validation, vector building, model inference.

Reusable outside route handlers (e.g. tests, batch jobs). Raises HTTPException
for validation failures so routes can pass through.
"""

from typing import Any, Dict, List, Tuple

from fastapi import HTTPException

from src.serve.state import ServeContext


def unknown_ticker_detail(ctx: ServeContext, requested: str) -> Dict[str, Any]:
    """Structured 400 body for unknown ticker: list of known tickers and count."""
    known = sorted(ctx.ticker_to_idx.keys())
    return {
        "error": "unknown_ticker",
        "message": f"Ticker '{requested}' is not in the trained ticker set.",
        "requested_ticker": requested,
        "known_tickers": known,
        "count": len(known),
    }


def validate_feature_input(
    ctx: ServeContext,
    received: Dict[str, Any],
    *,
    strict: bool = True,
) -> None:
    """
    Validate received keys against trained feature_columns.
    strict=True: exact match (no missing, no extra).
    strict=False: allow ticker + price columns only; ticker one-hot injected. Ticker must be in run record.
    Raises HTTPException(400) on mismatch.
    """
    expected_set = set(ctx.feature_columns)
    received_set = set(received.keys()) if received else set()
    missing = expected_set - received_set
    ticker_set = set(ctx.ticker_columns)
    if not strict and ticker_set and "ticker" in received_set:
        missing = missing - ticker_set
        ticker_val = str(received.get("ticker", "")).strip().upper()
        if ticker_val and ticker_val not in ctx.ticker_to_idx:
            raise HTTPException(status_code=400, detail=unknown_ticker_detail(ctx, ticker_val))
    extra = received_set - expected_set
    if missing:
        detail = (
            "Feature schema mismatch: expected vs received. "
            f"Expected {sorted(ctx.feature_columns)}; received {sorted(received_set)}. "
            f"Missing: {sorted(missing)}. Extra: {sorted(extra)}."
        )
        raise HTTPException(status_code=400, detail=detail)
    if strict and extra:
        detail = (
            "Feature schema mismatch: expected vs received. "
            f"Expected {sorted(ctx.feature_columns)}; received {sorted(received_set)}. "
            f"Missing: {sorted(missing)}. Extra: {sorted(extra)}."
        )
        raise HTTPException(status_code=400, detail=detail)


def row_to_feature_vector(ctx: ServeContext, row: Dict[str, Any]) -> List[float]:
    """Build feature vector in trained order; ticker one-hot from row['ticker'] when column not in row."""
    out: List[float] = []
    ticker_val = str(row.get("ticker", "")).strip().upper() if row.get("ticker") is not None else ""
    for c in ctx.feature_columns:
        if c in ctx.ticker_columns and ctx.ticker_to_idx and (c not in row or row.get(c) is None):
            idx = ctx.ticker_columns.index(c)
            out.append(1.0 if ctx.ticker_to_idx.get(ticker_val) == idx else 0.0)
        else:
            out.append(float(row.get(c, 0)))
    return out


def predict_one(ctx: ServeContext, feature_vector: List[float]) -> Tuple[float, float]:
    """Run model on one feature vector (trained order); return (prediction_score, confidence)."""
    import numpy as np

    scaler = ctx.run_record.get("scaler", {})
    mean = np.array(scaler.get("mean", [0.0] * ctx.expected_dim), dtype=np.float32)
    scale = np.array(scaler.get("scale", [1.0] * ctx.expected_dim), dtype=np.float32)
    X = np.array([feature_vector], dtype=np.float32)
    X_n = (X - mean) / scale
    pred = ctx.model.predict(X_n, verbose=0)
    score = float(pred.flatten()[0])
    confidence = 0.5 + 0.5 * (1.0 - min(1.0, abs(score)))
    return score, confidence
