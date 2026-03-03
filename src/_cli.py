"""Shared CLI helpers: config loading, config hashes, git context, and structured stage logging."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Repo root: src/_cli.py -> parents[1] = repo root
_REPO_ROOT = Path(__file__).resolve().parents[1]

# Default config when none specified (recruiter demo on real sample timeline, offline, no API keys)
DEFAULT_CONFIG_PATH = "configs/recruiter_demo_real.yaml"


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load YAML config from configs/; merge with defaults."""
    path = Path(config_path) if config_path else _REPO_ROOT / DEFAULT_CONFIG_PATH
    if not path.is_absolute():
        path = _REPO_ROOT / path
    if not path.exists():
        print(f"Warning: config not found at {path}, using defaults (no mode set).", file=sys.stderr)
        return _default_config()
    try:
        import yaml
        with open(path) as f:
            out = yaml.safe_load(f) or _default_config()
            return out
    except Exception as e:
        print(f"Warning: could not load config from {path}: {e}", file=sys.stderr)
        return _default_config()


def _default_config() -> Dict[str, Any]:
    return {
        "tickers": {"symbols": ["AAPL", "MSFT", "GOOGL"]},
        "time_horizon": {"train_end": "2023-12-31", "test_start": "2024-01-01"},
        "feature_windows": {"lookback_days": 21, "news_lookback_days": 7},
        "training": {"epochs": 50, "batch_size": 32, "learning_rate": 0.001},
    }


def _canonicalize_for_hash(obj: Any) -> Any:
    """Recursively normalize config for stable hashing (sort keys; exclude internal keys)."""
    if isinstance(obj, dict):
        return {k: _canonicalize_for_hash(v) for k, v in sorted(obj.items()) if k != "_config_path"}
    if isinstance(obj, list):
        return [_canonicalize_for_hash(x) for x in obj]
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    return str(obj)


def config_hash_from_file(path: Path) -> str:
    """Hash the exact file content (e.g. YAML) for reproducibility. Returns SHA-256 hex."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def config_hash_from_dict(config: Dict[str, Any]) -> str:
    """Stable hash of config dict (canonical JSON). Use when config path is not available."""
    canonical = _canonicalize_for_hash(config)
    blob = json.dumps(canonical, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def get_git_commit(repo_root: Optional[Path] = None) -> Optional[str]:
    """Return current git HEAD commit hash, or None if not a repo or git unavailable."""
    root = Path(repo_root) if repo_root else _REPO_ROOT
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=root,
            timeout=5,
        )
        if out.returncode == 0 and out.stdout:
            return out.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


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
