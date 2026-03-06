"""
Single source for repo root and config-driven paths.

Use repo_root() and get_paths(config) instead of Path(__file__).parents[N]
so that path resolution stays correct if modules are moved.
"""

from pathlib import Path
from typing import Any, Dict

# core/paths.py -> parents[0]=core, parents[1]=src, parents[2]=repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    """Return the repository root directory (project root)."""
    return _REPO_ROOT


def get_paths(config: Dict[str, Any]) -> Dict[str, Path]:
    """
    Resolve paths from config, relative to repo root.
    Returns dict with: repo_root, processed_path, models_path, reports_path, data_raw.
    """
    root = repo_root()
    paths_cfg = config.get("paths", {})
    processed = paths_cfg.get("data_processed", "data/processed")
    models = paths_cfg.get("models", "models")
    reports = paths_cfg.get("reports", "reports")
    data_raw = paths_cfg.get("data_raw", "data/sample")

    def resolve(p: str) -> Path:
        path = Path(p)
        return (root / path) if not path.is_absolute() else path

    return {
        "repo_root": root,
        "processed_path": resolve(processed),
        "models_path": resolve(models),
        "reports_path": resolve(reports),
        "data_raw": resolve(data_raw),
    }
