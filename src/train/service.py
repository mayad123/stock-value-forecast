"""
Training service: single entry point for training a model on processed data.

Inputs: config dict, optional path overrides, optional version hint, optional log.
Outputs: run_id (str). Raises on missing data or training failure.
No global state; safe to call from orchestration or tests.
"""

from pathlib import Path
from typing import Any, Callable, Dict, Optional


def train(
    config: Dict[str, Any],
    *,
    processed_root: Optional[Path] = None,
    models_root: Optional[Path] = None,
    dataset_version_hint: str = "latest",
    log: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Load processed train/val, train model, save artifact and run record.

    Returns:
        run_id (directory name under models/).

    Raises:
        FileNotFoundError: if processed data or version missing.
        ValueError: if no training data or invalid schema.
    """
    from src.train.train import run_training

    return run_training(
        config,
        processed_root=processed_root,
        models_root=models_root,
        dataset_version_hint=dataset_version_hint,
        log=log,
    )
