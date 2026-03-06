"""Shared CLI helpers: config hashes, git context, and stage logging. Config loading in src.config."""

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load config from YAML + defaults. See src.config.loader for resolution order."""
    from src.config.loader import load_config as _load
    return _load(config_path)


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
    if repo_root is not None:
        root = Path(repo_root)
    else:
        from src.core.paths import repo_root as _repo_root
        root = _repo_root()
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
    """Emit a structured log line for a pipeline stage (uses pipeline logger)."""
    from src.logging_config import stage_log as _log
    _log(stage, message)


def stage_done(stage: str) -> None:
    """Emit stage completion (uses pipeline logger)."""
    from src.logging_config import stage_done as _done
    _done(stage)


def require_live_apis_keys(config: Dict[str, Any]) -> None:
    """When mode is live_apis, require API keys from env. See src.config.secrets."""
    from src.config.secrets import require_live_apis_keys as _require
    _require(config)
