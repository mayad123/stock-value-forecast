"""Load a trained SavedModel and run record for evaluation (same metrics layer)."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import tensorflow as tf


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
    Apply scaler from run record and run model.predict. X_df must have run_record['feature_columns'].
    Returns 1d array of predictions (same order as X_df).
    """
    feature_cols = run_record.get("feature_columns", [])
    scaler = run_record.get("scaler", {})
    mean = np.array(scaler.get("mean", [0.0] * len(feature_cols)), dtype=np.float32)
    scale = np.array(scaler.get("scale", [1.0] * len(feature_cols)), dtype=np.float32)
    X = X_df[feature_cols].fillna(0).astype(np.float32).values
    X_n = (X - mean) / scale
    pred = model.predict(X_n, verbose=0)
    return pred.flatten()
