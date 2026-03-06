"""
Typed views over config sections (optional; use for clarity and IDE support).

Stages can keep using config.get("paths", {}) etc.; these types document the shape
and can be used where we want explicit validation or accessors.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict


class PathsConfig(TypedDict, total=False):
    """Paths section: all relative to repo root unless absolute."""

    data_raw: str
    data_processed: str
    data_features: str
    models: str
    reports: str


class TimeHorizonConfig(TypedDict, total=False):
    """Time horizon / split boundaries (YYYY-MM-DD strings)."""

    train_end: str
    val_start: str
    val_end: str
    test_start: str
    ingest_start: str


class TrainingConfig(TypedDict, total=False):
    """Training hyperparameters from config."""

    epochs: int
    batch_size: int
    learning_rate: float
    validation_split: float
    early_stopping_patience: int
    seed: int


class EvalConfig(TypedDict, total=False):
    """Eval section: version hint, walk-forward, run id override."""

    processed_version: str
    tensorflow_run_id: str
    min_train_days: int
    fold_size_days: int
    step_size_days: int
    walk_forward: Dict[str, Any]


def get_paths_config(config: Dict[str, Any]) -> Dict[str, Path]:
    """
    Resolve paths section against repo root. Returns dict of name -> Path.
    Uses core.paths.get_paths() logic for consistency.
    """
    from src.core.paths import get_paths
    return get_paths(config)


def get_tickers(config: Dict[str, Any]) -> List[str]:
    """Return ticker symbols list; empty if missing."""
    return list(config.get("tickers", {}).get("symbols", []))


def get_mode(config: Dict[str, Any]) -> Optional[str]:
    """Return config mode (recruiter_demo, live_apis, or None)."""
    return config.get("mode")
