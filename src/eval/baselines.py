"""
Baseline predictors for the trend (forward-return) task.
All expose a common interface: fit(train_df) and predict(test_df) -> y_pred array.
"""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# Use same feature/target names as feature pipeline
from src.features.price_features import FEATURE_NAMES, TARGET_NAME


def _get_X_y(df: pd.DataFrame, feature_cols: Optional[List[str]] = None) -> tuple:
    """Extract feature matrix and target; fill NaN features with 0 for robustness."""
    feature_cols = feature_cols or [c for c in FEATURE_NAMES if c in df.columns]
    X = df[feature_cols].fillna(0).astype(float)
    y = df[TARGET_NAME].astype(float)
    return X, y


# ----- Naive baseline -----


def predict_naive(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    strategy: str = "zero",
) -> np.ndarray:
    """
    Naive baseline: no trend (predict constant).
    strategy: "zero" -> predict 0 for all; "mean" -> predict train mean of target.
    """
    if strategy == "mean" and len(train_df) > 0:
        constant = train_df[TARGET_NAME].astype(float).mean()
    else:
        constant = 0.0
    return np.full(len(test_df), constant, dtype=float)


# ----- Heuristic baseline -----


def predict_heuristic(train_df: pd.DataFrame, test_df: pd.DataFrame) -> np.ndarray:
    """
    Simple heuristic: use last observed 1d return as proxy for next return.
    Predict return_1d for each test row (persistence of recent momentum).
    """
    if "return_1d" not in test_df.columns:
        return np.zeros(len(test_df), dtype=float)
    out = test_df["return_1d"].fillna(0).astype(float).values
    return out


# ----- Simple ML baseline -----


def predict_simple_ml(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
) -> np.ndarray:
    """
    Simple ML baseline: linear regression on the same features, fit on train only.
    """
    try:
        from sklearn.linear_model import LinearRegression
    except ImportError:
        return np.full(len(test_df), 0.0, dtype=float)  # no sklearn -> fallback to zero

    feature_cols = feature_cols or [c for c in FEATURE_NAMES if c in train_df.columns and c in test_df.columns]
    if not feature_cols:
        return np.full(len(test_df), 0.0, dtype=float)

    X_train, y_train = _get_X_y(train_df, feature_cols)
    X_test, _ = _get_X_y(test_df, feature_cols)
    if X_test.shape[1] != X_train.shape[1]:
        X_test = test_df[feature_cols].fillna(0).astype(float)

    model = LinearRegression()
    model.fit(X_train, y_train)
    return model.predict(X_test).astype(float)


# ----- Registry for backtest -----


def list_baseline_names() -> List[str]:
    return ["naive", "heuristic", "simple_ml"]


def get_baseline_predictions(
    name: str,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> np.ndarray:
    """Return y_pred for the given baseline name."""
    if name == "naive":
        return predict_naive(train_df, test_df)
    if name == "heuristic":
        return predict_heuristic(train_df, test_df)
    if name == "simple_ml":
        return predict_simple_ml(train_df, test_df)
    raise ValueError(f"Unknown baseline: {name}. Choose from {list_baseline_names()}")
