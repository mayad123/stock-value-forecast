"""
Typed data contracts for pipeline and API boundaries.

Use these TypedDicts and dataclasses where they clarify inputs/outputs.
Internal code can still use Dict[str, Any]; types document the expected shape.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


# ----- Run record (training artifact) -----


class ScalerDict(TypedDict, total=False):
    """Scaler stored in run_record; applied at inference."""

    mean: List[float]
    scale: List[float]


class RunRecord(TypedDict, total=False):
    """Shape of run_record.json produced by training. Keys used by load/predict/serve."""

    run_id: str
    config_hash: str
    git_commit_hash: Optional[str]
    dataset_version: str
    feature_columns: List[str]
    ticker_columns: List[str]
    ticker_to_idx: Dict[str, int]
    ticker_encoding_fingerprint: str
    scaler: ScalerDict
    target: Dict[str, Any]
    config: Dict[str, Any]
    feature_manifest_path: Optional[str]
    split_boundaries: Dict[str, Any]
    model_path: Optional[str]
    model_input_shape: List[Optional[int]]


# ----- Feature manifest (processed dataset metadata) -----


class FeatureManifest(TypedDict, total=False):
    """Shape of feature_manifest.json next to features.csv."""

    raw_dataset_version: str
    feature_columns: List[str]
    split_boundaries: Dict[str, str]
    feature_windows: Dict[str, Any]
    split_counts: Dict[str, int]


# ----- Evaluation metrics (per-model) -----


class ModelMetrics(TypedDict, total=False):
    """Metrics dict returned by compute_metrics; used in backtest summary."""

    mse: float
    rmse: float
    mae: float
    r2: float
    directional_accuracy: float
    ic: float
    n_samples: int


# ----- Backtest result -----


class BacktestSummary(TypedDict, total=False):
    """Shape of the summary dict returned by run_backtest (single-window or aggregate)."""

    dataset_version: str
    models: Dict[str, Optional[ModelMetrics]]
    n_test: int
    train_end: Optional[str]
    val_start: Optional[str]
    val_end: Optional[str]
    test_start: Optional[str]


# ----- Feature importance result -----


class FeatureImportanceItem(TypedDict, total=False):
    """One row in feature_importance list."""

    feature: str
    importance: float
    std: float


class FeatureImportanceResult(TypedDict, total=False):
    """Shape of feature_importance artifact (JSON) and GET /feature_importance response."""

    dataset_version: str
    model_run_id: str
    n_eval_samples: int
    metric: str
    n_repeats: int
    feature_importance: List[FeatureImportanceItem]
