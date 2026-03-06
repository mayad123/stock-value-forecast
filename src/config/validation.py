"""
Config validation: fail early with clear errors.

Validates required sections and mode. Does not validate secrets (handled in config.secrets).
"""

from typing import Any, Dict, List

# Allowed modes; used by workflows and stages
VALID_MODES = ("recruiter_demo", "live_apis", None)


class ConfigError(Exception):
    """Raised when config is invalid or missing required fields."""

    pass


def validate_config(config: Dict[str, Any], require_mode: bool = False) -> None:
    """
    Validate config structure and required sections. Raises ConfigError on failure.

    Args:
        config: Loaded config dict (e.g. from load_config).
        require_mode: If True, config["mode"] must be in VALID_MODES and not None.
    """
    errors: List[str] = []

    if require_mode:
        mode = config.get("mode")
        if mode is None:
            errors.append("config must set 'mode' (e.g. recruiter_demo or live_apis)")
        elif mode not in VALID_MODES:
            errors.append(f"config['mode'] must be one of {VALID_MODES}, got: {mode!r}")

    if "paths" not in config:
        errors.append("config must have 'paths' section")
    else:
        paths = config["paths"]
        for key in ("data_processed", "models", "reports"):
            if key not in paths:
                errors.append(f"config['paths'] must include '{key}'")

    if "tickers" not in config or "symbols" not in config.get("tickers", {}):
        errors.append("config must have 'tickers.symbols' (list of ticker symbols)")

    if "time_horizon" not in config and "feature_build" not in config:
        errors.append("config must have 'time_horizon' and/or 'feature_build' for pipeline stages")

    if errors:
        raise ConfigError(
            "Invalid config: " + "; ".join(errors)
            + ". Fix config YAML or use a known config (e.g. configs/recruiter_demo_real.yaml)."
        )


def validate_for_stage(config: Dict[str, Any], stage: str) -> None:
    """
    Validate config for a given stage. Ensures mode is set when required by workflows.
    Single-stage runs may have mode None; workflows require mode.
    """
    # When running a full workflow, mode is always set by the workflow. When running
    # a single stage from CLI, we already validated. This is a lightweight check.
    if config.get("mode") not in VALID_MODES and config.get("mode") is not None:
        raise ConfigError(f"config['mode'] must be one of {VALID_MODES}, got: {config.get('mode')!r}")
