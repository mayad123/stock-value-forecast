"""
Feature-building service: single entry point for building processed features from raw data.

Inputs: config dict, optional path overrides, optional log callback.
Outputs: processed dataset version (str). Raises on missing data or validation errors.
No global state; safe to call from orchestration or tests.
"""

from pathlib import Path
from typing import Any, Callable, Dict, Optional


def build_features(
    config: Dict[str, Any],
    *,
    raw_root: Optional[Path] = None,
    processed_root: Optional[Path] = None,
    log: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Build features from raw normalized prices, write processed dataset and manifest.

    Returns:
        Processed dataset version (e.g. raw version for 1:1 link).

    Raises:
        FileNotFoundError: if raw data or manifests missing.
        TimeOrderingError, LeakageError: from split validation.
    """
    from src.features.price_features import run_build_features

    return run_build_features(
        config,
        raw_root=raw_root,
        processed_root=processed_root,
        log=log,
    )
