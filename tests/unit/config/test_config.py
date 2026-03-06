"""Tests for centralized config: loader, validation, secrets."""

import pytest

from src.config.loader import load_config
from src.config.validation import ConfigError, validate_config


def test_load_config_merges_defaults():
    """Load config returns dict with expected top-level keys from defaults or file."""
    config = load_config(None)
    assert "paths" in config
    assert "tickers" in config
    assert "time_horizon" in config
    assert "feature_windows" in config
    assert config["paths"]["data_processed"] == "data/processed"
    assert "symbols" in config["tickers"]


def test_load_config_from_path(project_root):
    """Load config from explicit path (relative to repo root)."""
    config = load_config(str(project_root / "configs/recruiter_demo_real.yaml"))
    assert config.get("mode") == "recruiter_demo"
    assert "paths" in config
    assert "AAPL" in config["tickers"]["symbols"]


def test_validate_config_accepts_valid():
    """Valid config (paths, tickers, time_horizon) passes validation."""
    config = {
        "paths": {"data_processed": "x", "models": "y", "reports": "z"},
        "tickers": {"symbols": ["AAPL"]},
        "time_horizon": {"train_end": "2023-12-31"},
    }
    validate_config(config, require_mode=False)


def test_validate_config_requires_mode_when_required():
    """When require_mode=True, mode must be set and valid."""
    config = {
        "paths": {"data_processed": "x", "models": "y", "reports": "z"},
        "tickers": {"symbols": ["AAPL"]},
        "time_horizon": {},
    }
    validate_config(config, require_mode=False)
    with pytest.raises(ConfigError, match="mode"):
        validate_config(config, require_mode=True)
    config["mode"] = "recruiter_demo"
    validate_config(config, require_mode=True)


def test_validate_config_fails_missing_paths():
    """Missing paths section raises ConfigError."""
    config = {"tickers": {"symbols": []}, "time_horizon": {}}
    with pytest.raises(ConfigError, match="paths"):
        validate_config(config)


def test_validate_config_fails_missing_tickers_symbols():
    """Missing tickers.symbols raises ConfigError."""
    config = {
        "paths": {"data_processed": "x", "models": "y", "reports": "z"},
        "time_horizon": {},
    }
    with pytest.raises(ConfigError, match="tickers"):
        validate_config(config)


def test_validate_config_fails_invalid_mode():
    """Invalid mode value raises when require_mode=True."""
    config = {
        "mode": "invalid",
        "paths": {"data_processed": "x", "models": "y", "reports": "z"},
        "tickers": {"symbols": ["AAPL"]},
        "time_horizon": {},
    }
    with pytest.raises(ConfigError, match="mode"):
        validate_config(config, require_mode=True)


def test_secrets_from_env_only():
    """API keys are read from environment, not from config."""
    from src.config.secrets import get_api_keys

    keys = get_api_keys({})
    assert "ALPHAVANTAGE_API_KEY" in keys
    assert "MARKETAUX_API_KEY" in keys
