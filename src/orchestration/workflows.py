"""
Pipeline workflows: predefined stage sequences for demo, demo-real, and live.

Each workflow loads/validates config and runs stages in order. Train runs in a
subprocess so TensorFlow stderr can be filtered. Use run_stage() for a single
stage; use these for full pipelines.
"""

import os
import subprocess
import sys
from typing import Any, Dict

from src.core.paths import repo_root
from src.logging_config import get_logger

# Config file names (relative to repo root)
DEMO_CONFIG = "configs/recruiter_demo_real.yaml"
DEMO_REAL_CONFIG = "configs/recruiter_demo_real.yaml"
LIVE_CONFIG = "configs/live_apis.yaml"

# Stage order per workflow (demo skips ingest; live runs ingest first)
RUN_DEMO_STAGES = ("build-features", "train", "backtest")
RUN_DEMO_REAL_STAGES = ("validate-prices", "build-manifest", "build-features", "train", "backtest")
RUN_LIVE_STAGES = ("ingest", "build-features", "train", "backtest")

# Substrings in stderr that we filter out (TensorFlow C++ mutex noise)
TF_STDERR_FILTER = ("mutex.cc", "Lock blocking")


def _run_train_subprocess(config_path: str) -> None:
    """Run 'python run.py --config CONFIG train' in a subprocess; filter TF mutex lines from stderr."""
    root = repo_root()
    cmd = [sys.executable, str(root / "run.py"), "--config", config_path, "train"]
    env = os.environ.copy()
    env["RUN_TRAIN_SUBPROCESS"] = "1"
    env.setdefault("CUDA_VISIBLE_DEVICES", "")
    env.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    env.setdefault("TF_NUM_INTEROP_THREADS", "1")
    env.setdefault("TF_NUM_INTRAOP_THREADS", "1")
    proc = subprocess.Popen(
        cmd,
        cwd=str(root),
        env=env,
        stdout=sys.stdout,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    def read_stderr():
        for line in proc.stderr:
            if not any(s in line for s in TF_STDERR_FILTER):
                sys.stderr.write(line)
                sys.stderr.flush()

    import threading
    t = threading.Thread(target=read_stderr)
    t.daemon = True
    t.start()
    t.join()
    ret = proc.wait()
    if ret != 0:
        sys.exit(ret)


def _run_stage(stage_name: str, config: Dict[str, Any], stages: Dict[str, tuple]) -> None:
    """Invoke a single stage by name (module, attr)."""
    module_name, attr = stages[stage_name]
    mod = __import__(module_name, fromlist=[attr])
    getattr(mod, attr)(config)


def run_demo(config: Dict[str, Any], stages: Dict[str, tuple], config_path: str) -> None:
    """Run demo workflow: validate-prices preflight, then build-features -> train -> backtest."""
    from src.data.validate_prices_csv import run_validate_prices, ValidationError

    try:
        run_validate_prices(config)
    except ValidationError as e:
        get_logger("workflow").error("Validate-prices: %s", e)
        sys.exit(1)

    for s in RUN_DEMO_STAGES:
        if s == "train":
            _run_train_subprocess(config_path)
            continue
        _run_stage(s, config, stages)


def run_demo_real(config: Dict[str, Any], stages: Dict[str, tuple], config_path: str) -> None:
    """Run demo-real workflow: validate-prices, build-manifest, then build-features -> train -> backtest."""
    from src.data.validate_prices_csv import run_validate_prices, ValidationError
    from src.data.build_manifest import run_build_manifest

    try:
        run_validate_prices(config)
    except ValidationError as e:
        get_logger("workflow").error("Validate-prices: %s", e)
        sys.exit(1)

    dataset_version = config.get("feature_build", {}).get("raw_dataset_version", "demo_real_v1")
    try:
        run_build_manifest(config, dataset_version=dataset_version)
    except (FileNotFoundError, ValueError) as e:
        get_logger("workflow").error("Build-manifest: %s", e)
        sys.exit(1)

    for s in ("build-features", "train", "backtest"):
        if s == "train":
            _run_train_subprocess(config_path)
            continue
        _run_stage(s, config, stages)


def run_live(config: Dict[str, Any], stages: Dict[str, tuple], config_path: str) -> None:
    """Run live workflow: require API keys, then ingest -> build-features -> train -> backtest."""
    from src.config import require_live_apis_keys

    require_live_apis_keys(config)

    for s in RUN_LIVE_STAGES:
        if s == "train":
            _run_train_subprocess(config_path)
            continue
        _run_stage(s, config, stages)
