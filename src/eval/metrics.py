"""
Shared evaluation metrics for the trend prediction task (regression + directional).
Used by baselines and TensorFlow models so all are comparable.
"""

from typing import List, Union

import numpy as np

from src.types import ModelMetrics


def compute_metrics(
    y_true: Union[List[float], np.ndarray],
    y_pred: Union[List[float], np.ndarray],
) -> ModelMetrics:
    """
    Compute regression and directional metrics for continuous predictions.
    y_true, y_pred: 1d arrays of real-valued targets/predictions (e.g. forward return).
    Returns a dict suitable for JSON serialization and comparison across models.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if y_true.shape != y_pred.shape or y_true.ndim != 1:
        raise ValueError("y_true and y_pred must be 1d arrays of the same length")

    n = len(y_true)
    if n == 0:
        # No samples -> all metrics undefined; use 0.0 for ic to avoid downstream errors
        return {
            "mse": float("nan"),
            "rmse": float("nan"),
            "mae": float("nan"),
            "r2": float("nan"),
            "directional_accuracy": float("nan"),
            "ic": 0.0,
            "n_samples": 0,
        }

    # Regression
    mse = float(np.mean((y_true - y_pred) ** 2))
    rmse = float(np.sqrt(mse))
    mae = float(np.mean(np.abs(y_true - y_pred)))
    # R²
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else float("nan")

    # Directional: correct sign (or both zero)
    sign_true = np.sign(y_true)
    sign_pred = np.sign(y_pred)
    # Treat 0 as correct when both 0
    same_sign = (sign_true == sign_pred) | ((sign_true == 0) & (sign_pred == 0))
    directional_accuracy = float(np.mean(same_sign))

    # Information Coefficient (IC): correlation between y_pred and y_true.
    # When either side has zero variance, correlation is undefined; use 0.0 so consumers don't error.
    if np.std(y_true) == 0 or np.std(y_pred) == 0:
        ic = 0.0
    else:
        ic = float(np.corrcoef(y_true, y_pred)[0, 1])

    return {
        "mse": round(mse, 10),
        "rmse": round(rmse, 10),
        "mae": round(mae, 10),
        "r2": round(r2, 10) if not np.isnan(r2) else r2,
        "directional_accuracy": round(directional_accuracy, 6),
        "ic": round(ic, 6),
        "n_samples": n,
    }


def metrics_keys() -> List[str]:
    """Canonical list of metric keys for consistent reporting."""
    return ["mse", "rmse", "mae", "r2", "directional_accuracy", "ic", "n_samples"]
