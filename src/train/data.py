"""Load processed train/val splits for TensorFlow training."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.features.price_features import FEATURE_NAMES, TARGET_NAME


def load_train_val(
    processed_root: Path,
    dataset_version: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load features.csv and return (train_df, val_df)."""
    path = processed_root / dataset_version / "features.csv"
    if not path.exists():
        raise FileNotFoundError(f"Features not found: {path}")
    df = pd.read_csv(path)
    if "split" not in df.columns:
        raise ValueError("Features CSV must have 'split' column")
    train_df = df[df["split"] == "train"].copy()
    val_df = df[df["split"] == "val"].copy()
    return train_df, val_df


def load_feature_manifest(processed_root: Path, dataset_version: str) -> Dict[str, Any]:
    """Load feature_manifest.json for run record."""
    path = processed_root / dataset_version / "feature_manifest.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def get_X_y(
    df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract feature matrix and target; fill NaN with 0. Uses feature_cols if provided, else FEATURE_NAMES present in df."""
    if feature_cols is None:
        feature_cols = [c for c in FEATURE_NAMES if c in df.columns]
    X = df[feature_cols].fillna(0).astype(np.float32)
    y = df[TARGET_NAME].astype(np.float32).values
    return X.values, y
