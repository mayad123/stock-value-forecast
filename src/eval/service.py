"""
Evaluation service: single entry point for backtest and feature importance.

Inputs: config dict, optional path overrides, optional version hint, optional log.
Outputs: result dict (BacktestSummary or FeatureImportanceResult shape). Raises on missing data.
No global state; safe to call from orchestration or tests.
"""

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from src.types import FeatureImportanceResult


def backtest(
    config: Dict[str, Any],
    *,
    processed_root: Optional[Path] = None,
    dataset_version_hint: str = "latest",
    log: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Run backtest: baselines and optional TF model on test split; write metrics and predictions.

    Returns:
        Summary dict (dataset_version, models metrics, etc.).

    Raises:
        FileNotFoundError: if processed data or version missing.
    """
    from src.eval.backtest import run_backtest

    return run_backtest(
        config,
        processed_root=processed_root,
        dataset_version_hint=dataset_version_hint,
        log=log,
    )


def feature_importance(
    config: Dict[str, Any],
    *,
    processed_root: Optional[Path] = None,
    dataset_version_hint: str = "latest",
    n_repeats: int = 5,
    log: Optional[Callable[[str], None]] = None,
) -> FeatureImportanceResult:
    """
    Compute permutation feature importance, write JSON/PNG to reports.

    Returns:
        Artifact dict (dataset_version, feature_importance list, etc.).

    Raises:
        FileNotFoundError: if processed data, version, or model missing.
    """
    from src.eval.feature_importance import run_feature_importance

    return run_feature_importance(
        config,
        processed_root=processed_root,
        dataset_version_hint=dataset_version_hint,
        n_repeats=n_repeats,
        log=log,
    )
