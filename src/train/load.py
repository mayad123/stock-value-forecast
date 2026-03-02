"""Load a trained SavedModel and run record for evaluation (same metrics layer)."""

import json
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
import tensorflow as tf


def _inject_ticker_onehot_if_needed(df: pd.DataFrame, run_record: Dict[str, Any]) -> pd.DataFrame:
    """If run_record has ticker encoding and df has 'ticker' but not ticker_* columns, add one-hot. Returns df (possibly modified copy)."""
    ticker_columns = run_record.get("ticker_columns") or []
    ticker_to_idx = run_record.get("ticker_to_idx") or {}
    if not ticker_columns or "ticker" not in df.columns:
        return df
    if all(c in df.columns for c in ticker_columns):
        return df
    df = df.copy()
    for col in ticker_columns:
        df[col] = 0.0
    for ticker, idx in ticker_to_idx.items():
        if idx < len(ticker_columns):
            col = ticker_columns[idx]
            df.loc[df["ticker"].astype(str) == ticker, col] = 1.0
    return df


def load_run_record(run_dir: Path) -> Dict[str, Any]:
    """Load run_record.json from a training run directory."""
    path = run_dir / "run_record.json"
    if not path.exists():
        raise FileNotFoundError(f"Run record not found: {path}")
    with open(path) as f:
        return json.load(f)


def load_trained_model(run_dir: Path) -> Tuple[tf.keras.Model, Dict[str, Any]]:
    """
    Load model and run record from models/{run_id}/. Supports model.keras (Keras 3) or saved_model/ (legacy).
    Returns (model, run_record). Use run_record['scaler'] and run_record['feature_columns'] for inference.
    """
    keras_path = run_dir / "model.keras"
    saved_model_path = run_dir / "saved_model"
    if keras_path.exists():
        model = tf.keras.models.load_model(keras_path)
    elif saved_model_path.exists():
        model = tf.keras.models.load_model(saved_model_path)
    else:
        raise FileNotFoundError(f"Model not found: expected {keras_path} or {saved_model_path}")
    record = load_run_record(run_dir)
    return model, record


def predict_with_trained_model(
    model: tf.keras.Model,
    run_record: Dict[str, Any],
    X_df: pd.DataFrame,
) -> np.ndarray:
    """
    Apply scaler from run record and run model.predict. X_df must have run_record['feature_columns'],
    or ticker + price columns so that ticker one-hot can be injected from run_record.
    Returns 1d array of predictions (same order as X_df).
    """
    X_df = _inject_ticker_onehot_if_needed(X_df, run_record)
    feature_cols = run_record.get("feature_columns", [])
    scaler = run_record.get("scaler", {})
    mean = np.array(scaler.get("mean", [0.0] * len(feature_cols)), dtype=np.float32)
    scale = np.array(scaler.get("scale", [1.0] * len(feature_cols)), dtype=np.float32)
    X = X_df[feature_cols].fillna(0).astype(np.float32).values
    X_n = (X - mean) / scale
    pred = model.predict(X_n, verbose=0)
    return pred.flatten()
