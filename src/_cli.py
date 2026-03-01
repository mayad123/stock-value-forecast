"""Shared CLI helpers: config loading and structured stage logging."""

from pathlib import Path
from typing import Any, Dict, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load YAML config from configs/; merge with defaults."""
    path = Path(config_path) if config_path else _REPO_ROOT.parent / "configs" / "default.yaml"
    if not path.is_absolute():
        path = _REPO_ROOT.parent / path
    if not path.exists():
        return _default_config()
    try:
        import yaml
        with open(path) as f:
            return yaml.safe_load(f) or _default_config()
    except Exception:
        return _default_config()


def _default_config() -> Dict[str, Any]:
    return {
        "tickers": {"symbols": ["AAPL", "MSFT", "GOOGL"]},
        "time_horizon": {"train_end": "2023-12-31", "test_start": "2024-01-01"},
        "feature_windows": {"lookback_days": 21, "news_lookback_days": 7},
        "training": {"epochs": 50, "batch_size": 32, "learning_rate": 0.001},
    }


def stage_log(stage: str, message: str) -> None:
    """Print a structured log line for a pipeline stage."""
    print(f"[{stage.upper()}] {message}")


def stage_done(stage: str) -> None:
    """Print stage completion line."""
    print(f"[{stage.upper()}] Done.")
