"""
Local data access: read report files (e.g. metrics JSON).

Used when a page needs file-based data (e.g. Model Overview / Fold Stability
reading reports/latest_metrics.json). API-first pages use api_client instead.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def load_json_file(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Load a JSON file. Returns (data, None) or (None, error_message).
    For invalid or missing file, returns (None, error_message).
    """
    if not path.exists():
        return None, f"File not found: {path}"
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None, "Invalid format (expected JSON object)."
        return data, None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"
    except OSError as e:
        return None, str(e)


def load_metrics_file(repo_root: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Load reports/latest_metrics.json. Returns (data, None) or (None, error_message).
    Validates that data has a 'models' dict.
    """
    path = repo_root / "reports" / "latest_metrics.json"
    data, err = load_json_file(path)
    if err:
        return None, err
    if data is None or not isinstance(data, dict):
        return None, "Invalid format (expected JSON object)."
    if not isinstance(data.get("models"), dict):
        return None, "File has no valid 'models' object."
    return data, None
