"""
Centralized configuration: loading, validation, secrets, and typed accessors.

Resolution order (see loader.py):
  1. Static defaults
  2. YAML file
  3. Runtime overrides (_config_path set by CLI)
  4. Secrets from environment only (never in YAML)

Use load_config() then validate_config() before passing config to stages.
"""

from src.config.loader import (
    DEFAULT_CONFIG_PATH,
    load_config,
    load_config_and_set_path,
)
from src.config.secrets import get_api_keys, get_serve_env_overrides, require_live_apis_keys
from src.config.validation import ConfigError, validate_config, validate_for_stage

from src._cli import (
    config_hash_from_dict,
    config_hash_from_file,
    get_git_commit,
    stage_done,
    stage_log,
)

__all__ = [
    "ConfigError",
    "DEFAULT_CONFIG_PATH",
    "get_api_keys",
    "get_serve_env_overrides",
    "load_config",
    "load_config_and_set_path",
    "require_live_apis_keys",
    "validate_config",
    "validate_for_stage",
    "config_hash_from_dict",
    "config_hash_from_file",
    "get_git_commit",
    "stage_done",
    "stage_log",
]
