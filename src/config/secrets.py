"""
Secrets and environment-based configuration.

Secrets are never read from YAML or stored in config. They are read from the
environment at use-time (e.g. ALPHAVANTAGE_API_KEY, MARKETAUX_API_KEY).
Runtime overrides for the serve layer (SERVE_MODELS_PATH, etc.) are also env-only.
"""

import os
import sys
from typing import Any, Dict, Optional

from src.logging_config import get_logger


def get_api_keys(config: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Read API keys from environment only. No defaults or hardcoding.

    Returns:
        Dict with keys ALPHAVANTAGE_API_KEY, MARKETAUX_API_KEY (value or None).
    """
    return {
        "ALPHAVANTAGE_API_KEY": os.environ.get("ALPHAVANTAGE_API_KEY", "").strip() or None,
        "MARKETAUX_API_KEY": os.environ.get("MARKETAUX_API_KEY", "").strip() or None,
    }


def require_live_apis_keys(config: Dict[str, Any]) -> None:
    """
    When mode is live_apis, require API keys from environment and exit with a
    clear message if missing. Call after loading config so live runs fail early.
    """
    if config.get("mode") != "live_apis":
        return
    keys = get_api_keys(config)
    missing = []
    if not keys["ALPHAVANTAGE_API_KEY"]:
        missing.append(
            "ALPHAVANTAGE_API_KEY (required for price ingest). "
            "Get a free key at https://www.alphavantage.co/support/#api-key"
        )
    if config.get("use_news") and not keys["MARKETAUX_API_KEY"]:
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
        get_logger("config").error("%s", msg)
        sys.exit(1)


def get_serve_env_overrides() -> Dict[str, Optional[str]]:
    """
    Read serve-layer overrides from environment (e.g. in Docker or cloud).
    Keys: SERVE_MODELS_PATH, SERVE_PROCESSED_PATH, SERVE_REPORTS_PATH, SERVE_SAMPLE_PRICES_PATH, MODEL_RUN_ID.
    """
    return {
        "SERVE_MODELS_PATH": os.environ.get("SERVE_MODELS_PATH", "").strip() or None,
        "SERVE_PROCESSED_PATH": os.environ.get("SERVE_PROCESSED_PATH", "").strip() or None,
        "SERVE_REPORTS_PATH": os.environ.get("SERVE_REPORTS_PATH", "").strip() or None,
        "SERVE_SAMPLE_PRICES_PATH": os.environ.get("SERVE_SAMPLE_PRICES_PATH", "").strip() or None,
        "MODEL_RUN_ID": os.environ.get("MODEL_RUN_ID", "").strip() or None,
    }
