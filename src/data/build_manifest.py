"""
Build a price manifest by scanning data/sample/prices_normalized/ (or config data_raw).
Ensures all ticker CSVs are included; paths are relative to the raw root so feature build
loads them correctly. Adding or removing a ticker CSV and rerunning updates the manifest.

Run: python run.py build-manifest --dataset-version demo_real_v1
"""

from pathlib import Path
from typing import Any, Dict, Optional

from src.data.manifest import generate_manifest


def run_build_manifest(
    config: Dict[str, Any],
    dataset_version: str,
    raw_root: Optional[Path] = None,
    prices_subdir: str = "prices_normalized",
    log: Any = None,
) -> Path:
    """
    Scan raw_root / prices_subdir for *.csv and write raw_root/manifests/{dataset_version}.json.
    Manifest includes dataset_version, normalized_paths (relative to raw_root), global date_range,
    and tickers. Paths are exactly as price_features.load_raw_normalized expects (raw_root / path).
    Returns the manifest path.
    """
    if log is None:
        from src.logging_config import get_logger
        _log = get_logger("build-manifest")
        def log(msg: str) -> None:
            _log.info("%s", msg)

    from src.core.paths import repo_root
    root = repo_root()
    paths_cfg = config.get("paths", {})
    data_raw = paths_cfg.get("data_raw", "data/sample")
    raw_root = raw_root or (root / data_raw if not Path(data_raw).is_absolute() else Path(data_raw))
    raw_root = raw_root.resolve()

    return generate_manifest(raw_root, dataset_version, prices_subdir=prices_subdir, log=log)
