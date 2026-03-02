"""Shared CLI helpers: config loading and structured stage logging."""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Default config when none specified (recruiter demo = offline, no API keys)
DEFAULT_CONFIG_PATH = "configs/recruiter_demo.yaml"


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load YAML config from configs/; merge with defaults."""
    path = Path(config_path) if config_path else _REPO_ROOT.parent / DEFAULT_CONFIG_PATH
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


def require_live_apis_keys(config: Dict[str, Any]) -> None:
    """
    When mode is live_apis, require API keys and exit with a clear message if missing.
    Call this after loading config so live_apis runs fail early.
    """
    missing = []
    if not os.environ.get("ALPHAVANTAGE_API_KEY", "").strip():
        missing.append(
            "ALPHAVANTAGE_API_KEY (required for price ingest). "
            "Get a free key at https://www.alphavantage.co/support/#api-key"
        )
    if config.get("use_news") and not os.environ.get("MARKETAUX_API_KEY", "").strip():
        missing.append(
            "MARKETAUX_API_KEY (required when use_news is true). "
            "Get a free key at https://www.marketaux.com/register"
        )
    if missing:
        msg = (
            "Config mode is 'live_apis' but required API keys are missing. "
            "Set them in .env or the environment:\n  - "
            + "\n  - ".join(missing)
        )
        print(msg, file=sys.stderr)
        sys.exit(1)
