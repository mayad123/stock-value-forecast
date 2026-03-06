"""
Serve context: read-only state after model and artifacts are loaded.

Holds everything the API needs for prediction, feature lookup, and response shaping.
Passed into service helpers so routing stays separate from business logic.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass(frozen=False)
class ServeContext:
    """Loaded model, run record, feature data, and paths. Set once at startup."""

    model: Any  # tf.keras.Model
    run_record: Dict[str, Any]
    run_id: str
    features_df: pd.DataFrame
    feature_columns: List[str]
    ticker_columns: List[str]
    ticker_to_idx: Dict[str, int]
    expected_dim: int
    schema_fingerprint: str
    reports_path: Path
    sample_prices_path: Path
    repo_root: Path

    @property
    def dataset_version(self) -> str:
        return str(self.run_record.get("dataset_version", ""))

    @property
    def has_ticker_encoding(self) -> bool:
        return bool(self.ticker_to_idx)
