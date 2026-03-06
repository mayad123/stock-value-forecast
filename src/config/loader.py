"""
Centralized configuration loading.

Resolution order (applied in sequence):
  1. Static defaults – minimal required keys so code never sees missing sections.
  2. YAML file – overrides defaults; path may be absolute or relative to repo root.
  3. Runtime overrides – e.g. _config_path set by CLI when a file path was provided.
  4. Secrets – never from YAML; always from environment (see config.secrets).
     ALPHAVANTAGE_API_KEY, MARKETAUX_API_KEY are read at use-time, not stored in config.

All stages receive the same merged dict. Use validate_config() after load to fail early
on invalid or missing required fields.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from src.core.paths import repo_root
from src.logging_config import get_logger

# Default config path when none specified (recruiter demo, offline)
DEFAULT_CONFIG_PATH = "configs/recruiter_demo_real.yaml"


def _default_config() -> Dict[str, Any]:
    """Minimal defaults so config.get("section", {}) never fails for expected keys."""
    return {
        "mode": None,
        "tickers": {"symbols": ["AAPL", "MSFT", "GOOGL"]},
        "time_horizon": {"train_end": "2023-12-31", "test_start": "2024-01-01"},
        "feature_windows": {"lookback_days": 21, "news_lookback_days": 7, "forward_return_days": 1},
        "paths": {
            "data_raw": "data/sample",
            "data_processed": "data/processed",
            "models": "models",
            "reports": "reports",
        },
        "feature_build": {"raw_dataset_version": "latest", "news_dataset_version": "latest"},
        "train": {"processed_version": "latest"},
        "eval": {"processed_version": "latest"},
        "training": {"epochs": 50, "batch_size": 32, "learning_rate": 0.001},
        "use_news": False,
    }


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge override into base. override wins; base is not mutated."""
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load config: defaults + YAML file. Single entry point for pipeline config.

    Args:
        config_path: Path to YAML file. If None, uses DEFAULT_CONFIG_PATH relative to repo root.
                    If relative, resolved against repo root.

    Returns:
        Merged config dict. Call validate_config() before passing to workflows/stages.
    """
    root = repo_root()
    path = Path(config_path) if config_path else root / DEFAULT_CONFIG_PATH
    if not path.is_absolute():
        path = root / path

    base = _default_config()
    if not path.exists():
        if config_path is not None:
            get_logger("config").warning("Config not found at %s, using defaults (no mode set).", path)
        return base

    try:
        import yaml
        with open(path) as f:
            from_file = yaml.safe_load(f) or {}
        merged = _deep_merge(base, from_file)
        return merged
    except Exception as e:
        raise RuntimeError(f"Failed to load config from {path}: {e}") from e


def load_config_and_set_path(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load config and set _config_path for reproducibility (hash, run records).
    Use when the CLI or orchestration has a known config file path.
    """
    root = repo_root()
    path = Path(config_path) if config_path else root / DEFAULT_CONFIG_PATH
    if not path.is_absolute():
        path = root / path
    config = load_config(config_path)
    config["_config_path"] = str(path.resolve())
    return config
