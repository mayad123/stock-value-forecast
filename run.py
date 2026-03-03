#!/usr/bin/env python3
"""
Single entry point for the ML pipeline.

Workflows (use these to avoid cross-mode accidents):
  demo   configs/recruiter_demo_real.yaml  build-features -> train -> backtest (no ingest, no API keys)
  live   configs/live_apis.yaml       ingest -> build-features -> train -> backtest (requires API keys)

Single stages (require --config unless using default): ingest | build-features | train | backtest | serve
  python run.py [--config CONFIG] <stage>

Loads .env from repo root if present (for ALPHAVANTAGE_API_KEY, MARKETAUX_API_KEY, etc.).
"""
# Reduce TensorFlow hangs: CPU-only, single-thread, quiet C++ logs (must be before any TF import)
import os
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")       # avoid GPU init that can block before first epoch
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")      # 3 = errors only (suppress mutex.cc Lock blocking)
os.environ.setdefault("TF_NUM_INTEROP_THREADS", "1")   # fewer threads => less lock contention
os.environ.setdefault("TF_NUM_INTRAOP_THREADS", "1")   # fewer threads => less lock contention

import subprocess
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load .env so API keys and optional overrides are available
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

DEMO_CONFIG = "configs/recruiter_demo_real.yaml"
DEMO_REAL_CONFIG = "configs/recruiter_demo_real.yaml"
LIVE_CONFIG = "configs/live_apis.yaml"

# Fixed stage order per workflow (demo never runs ingest; live runs ingest first)
RUN_DEMO_STAGES = ("build-features", "train", "backtest")
RUN_DEMO_REAL_STAGES = ("validate-prices", "build-manifest", "build-features", "train", "backtest")
RUN_LIVE_STAGES = ("ingest", "build-features", "train", "backtest")

# Substrings in stderr that we filter out (TensorFlow C++ "RAW" mutex line bypasses TF_CPP_MIN_LOG_LEVEL)
TF_STDERR_FILTER = ("mutex.cc", "Lock blocking")


def _run_train_subprocess_with_filtered_stderr(config_path: str) -> None:
    """Run 'python run.py --config CONFIG train' in a subprocess; filter TF mutex lines from stderr."""
    cmd = [sys.executable, str(REPO_ROOT / "run.py"), "--config", config_path, "train"]
    env = os.environ.copy()
    env["RUN_TRAIN_SUBPROCESS"] = "1"  # so child skips preflight (already done by parent)
    env.setdefault("CUDA_VISIBLE_DEVICES", "")
    env.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    env.setdefault("TF_NUM_INTEROP_THREADS", "1")
    env.setdefault("TF_NUM_INTRAOP_THREADS", "1")
    proc = subprocess.Popen(
        cmd,
        cwd=str(REPO_ROOT),
        env=env,
        stdout=sys.stdout,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    # Stream stderr and drop lines containing TF mutex noise
    def read_stderr():
        for line in proc.stderr:
            if not any(s in line for s in TF_STDERR_FILTER):
                sys.stderr.write(line)
                sys.stderr.flush()
    t = threading.Thread(target=read_stderr)
    t.daemon = True
    t.start()
    t.join()
    ret = proc.wait()
    if ret != 0:
        sys.exit(ret)


def _print_help() -> None:
    print("Usage: python run.py [--config CONFIG] <stage>")
    print("       python run.py demo | demo-real | live")
    print("")
    print("Workflows (explicit mode; config is fixed, no cross-mode):")
    print("  demo       configs/recruiter_demo_real.yaml        build-features -> train -> backtest")
    print("             (offline, no ingest, no API keys)")
    print("  demo-real  configs/recruiter_demo_real.yaml  validate-prices -> build-manifest -> build-features -> train -> backtest")
    print("             (real timeline, multi-ticker; versioned under reports/<dataset_version>/ and latest for UI)")
    print("  live       configs/live_apis.yaml             ingest -> build-features -> train -> backtest")
    print("             (ingest prices, optional news, then features/train/backtest; requires API keys)")
    print("")
    print("Single stages (use --config for live_apis; default config is recruiter_demo):")
    print("  ingest | build-features | train | backtest | serve | manifest [VERSION] | build-manifest | validate-prices [VERSION]")
    print("")
    print("Examples:")
    print("  make demo          # or: python run.py demo")
    print("  make live         # or: python run.py live")
    print("  python run.py --config configs/live_apis.yaml ingest")
    print("  python run.py manifest demo      # regenerate data/sample/manifests/demo.json from CSVs")
    print("  python run.py build-manifest --dataset-version demo_real_v1   # generate data/sample/manifests/demo_real_v1.json from all CSVs")
    print("  python run.py validate-prices demo   # validate prices_normalized CSVs, write reports/data_validation_demo.json")
    print("  python run.py demo-real             # full pipeline on real data; to avoid TF locking use: make demo-real or ./scripts/run-demo-real.sh")


def _parse_args(argv: list) -> tuple:
    """Return (config_path_or_none, stage, rest_positionals, dataset_version_or_none). Supports --config, --dataset-version, -h/--help."""
    args = argv[1:]
    if "-h" in args or "--help" in args:
        return None, "help", [], None
    config_path = None
    dataset_version = None
    while args:
        if args[0] == "--config" and len(args) >= 2:
            config_path = args[1]
            args = args[2:]
        elif args[0] == "--dataset-version" and len(args) >= 2:
            dataset_version = args[1]
            args = args[2:]
        else:
            break
    if not args:
        return config_path, None, [], dataset_version
    return config_path, args[0], args[1:], dataset_version


def main() -> None:
    stages = {
        "ingest": ("src.ingest", "run_ingest"),
        "build-features": ("src.features", "run_build_features"),
        "train": ("src.train", "run_train"),
        "backtest": ("src.eval", "run_backtest"),
        "serve": ("src.serve", "run_serve"),
    }
    workflows = ("demo", "demo-real", "live")

    config_path_arg, stage, rest_args, dataset_version_arg = _parse_args(sys.argv)
    if stage == "help":
        _print_help()
        sys.exit(0)
    if stage == "manifest":
        # manifest [VERSION]: regenerate manifest from prices_normalized/; VERSION defaults from config
        from src._cli import load_config
        from src.data.manifest import generate_manifest
        if config_path_arg:
            config_path = Path(config_path_arg)
            if not config_path.is_absolute():
                config_path = REPO_ROOT / config_path
            config = load_config(str(config_path))
        else:
            config = load_config(str(REPO_ROOT / DEMO_CONFIG))
        raw = config.get("paths", {}).get("data_raw", "data/sample")
        raw_root = REPO_ROOT / raw if not Path(raw).is_absolute() else Path(raw)
        version = rest_args[0] if rest_args else config.get("feature_build", {}).get("raw_dataset_version", "demo")
        try:
            generate_manifest(raw_root, version)
        except (FileNotFoundError, ValueError) as e:
            print(f"Manifest: {e}", file=sys.stderr)
            sys.exit(1)
        return
    if stage == "validate-prices":
        # validate-prices [VERSION]: validate prices_normalized CSVs, optional auto-fix descending, write report
        from src._cli import load_config
        from src.data.validate_prices_csv import run_validate_prices, ValidationError
        if config_path_arg:
            config_path = Path(config_path_arg)
            if not config_path.is_absolute():
                config_path = REPO_ROOT / config_path
            config = load_config(str(config_path))
        else:
            config = load_config(str(REPO_ROOT / DEMO_CONFIG))
        raw = config.get("paths", {}).get("data_raw", "data/sample")
        raw_root = REPO_ROOT / raw if not Path(raw).is_absolute() else Path(raw)
        version = rest_args[0] if rest_args else config.get("feature_build", {}).get("raw_dataset_version", "demo")
        try:
            run_validate_prices(config, raw_root=raw_root, dataset_version=version)
        except ValidationError as e:
            print(f"Validate-prices: {e}", file=sys.stderr)
            sys.exit(1)
        return
    if stage == "build-manifest":
        # build-manifest: requires --dataset-version; generates data/sample/manifests/<version>.json from all CSVs
        from src._cli import load_config
        from src.data.build_manifest import run_build_manifest
        version = dataset_version_arg
        if not version and len(rest_args) >= 2 and rest_args[0] == "--dataset-version":
            version = rest_args[1]
        elif not version and rest_args and not rest_args[0].startswith("-"):
            version = rest_args[0]
        if not version:
            print("Error: build-manifest requires --dataset-version (e.g. python run.py build-manifest --dataset-version demo_real_v1)", file=sys.stderr)
            sys.exit(1)
        if config_path_arg:
            config_path = Path(config_path_arg)
            if not config_path.is_absolute():
                config_path = REPO_ROOT / config_path
            config = load_config(str(config_path))
        else:
            config = load_config(str(REPO_ROOT / DEMO_CONFIG))
        try:
            run_build_manifest(config, dataset_version=version)
        except (FileNotFoundError, ValueError) as e:
            print(f"Build-manifest: {e}", file=sys.stderr)
            sys.exit(1)
        return
    if stage is None or (stage not in stages and stage not in workflows):
        _print_help()
        sys.exit(1)

    from src._cli import load_config, require_live_apis_keys

    # Workflows: fix config by mode to prevent cross-mode
    if stage == "demo":
        demo_path = REPO_ROOT / DEMO_CONFIG
        config = load_config(str(demo_path))
        config["_config_path"] = str(demo_path.resolve())
        if config.get("mode") != "recruiter_demo":
            print("Error: demo must use config with mode: recruiter_demo", file=sys.stderr)
            sys.exit(1)
        from src.data.validate_prices_csv import run_validate_prices, ValidationError
        try:
            run_validate_prices(config)
        except ValidationError as e:
            print(f"Validate-prices: {e}", file=sys.stderr)
            sys.exit(1)
        demo_config_path = str(REPO_ROOT / DEMO_CONFIG)
        for s in RUN_DEMO_STAGES:
            if s == "train":
                _run_train_subprocess_with_filtered_stderr(demo_config_path)
                continue
            module_name, attr = stages[s]
            mod = __import__(module_name, fromlist=[attr])
            getattr(mod, attr)(config)
        return

    if stage == "demo-real":
        # Full pipeline on real timeline: validate -> build-manifest -> build-features -> train -> backtest.
        # Uses recruiter_demo_real.yaml; dataset_version = demo_real_v1. Versioned under reports/<dataset_version>/ and latest.
        demo_real_path = REPO_ROOT / DEMO_REAL_CONFIG
        if not demo_real_path.exists():
            print(f"Error: config not found: {demo_real_path}", file=sys.stderr)
            sys.exit(1)
        config = load_config(str(demo_real_path))
        config["_config_path"] = str(demo_real_path.resolve())
        if config.get("mode") != "recruiter_demo":
            print("Error: demo-real must use config with mode: recruiter_demo", file=sys.stderr)
            sys.exit(1)
        dataset_version = config.get("feature_build", {}).get("raw_dataset_version", "demo_real_v1")
        from src.data.validate_prices_csv import run_validate_prices, ValidationError
        from src.data.build_manifest import run_build_manifest
        try:
            run_validate_prices(config)
        except ValidationError as e:
            print(f"Validate-prices: {e}", file=sys.stderr)
            sys.exit(1)
        try:
            run_build_manifest(config, dataset_version=dataset_version)
        except (FileNotFoundError, ValueError) as e:
            print(f"Build-manifest: {e}", file=sys.stderr)
            sys.exit(1)
        for s in ("build-features", "train", "backtest"):
            if s == "train":
                # Run train in subprocess so we can filter TensorFlow C++ "RAW" mutex line from stderr
                _run_train_subprocess_with_filtered_stderr(str(demo_real_path))
                continue
            module_name, attr = stages[s]
            mod = __import__(module_name, fromlist=[attr])
            getattr(mod, attr)(config)
        return

    if stage == "live":
        live_path = REPO_ROOT / LIVE_CONFIG
        config = load_config(str(live_path))
        config["_config_path"] = str(live_path.resolve())
        if config.get("mode") != "live_apis":
            print("Error: live must use config with mode: live_apis", file=sys.stderr)
            sys.exit(1)
        require_live_apis_keys(config)
        live_config_path = str(REPO_ROOT / LIVE_CONFIG)
        for s in RUN_LIVE_STAGES:
            if s == "train":
                _run_train_subprocess_with_filtered_stderr(live_config_path)
                continue
            module_name, attr = stages[s]
            mod = __import__(module_name, fromlist=[attr])
            getattr(mod, attr)(config)
        return

    # Single stage: use provided config or default recruiter_demo
    if config_path_arg:
        config_path = Path(config_path_arg)
        if not config_path.is_absolute():
            config_path = REPO_ROOT / config_path
        config = load_config(str(config_path))
        config["_config_path"] = str(config_path.resolve())
    else:
        default_path = REPO_ROOT / DEMO_CONFIG
        config = load_config(str(default_path))
        config["_config_path"] = str(default_path.resolve())

    if config.get("mode") == "live_apis":
        require_live_apis_keys(config)

    # Preflight: validate prices CSVs before build-features/train/backtest in demo mode (skip if we're the train subprocess)
    if stage not in ("build-features", "train", "backtest") or config.get("mode") != "recruiter_demo":
        pass
    elif os.environ.get("RUN_TRAIN_SUBPROCESS") == "1":
        pass  # parent already ran preflight
    else:
        from src.data.validate_prices_csv import run_validate_prices, ValidationError
        try:
            run_validate_prices(config)
        except ValidationError as e:
            msg = str(e)
            # In environments without demo CSVs (e.g. CI stub tests), allow the stage to run and fail
            # in its own way instead of exiting here, so CLI tests still see [BUILD-FEATURES]/[TRAIN]/[BACKTEST].
            if "Prices directory not found" in msg:
                print(f"Validate-prices (warning only): {msg}", file=sys.stderr)
            else:
                print(f"Validate-prices: {msg}", file=sys.stderr)
                sys.exit(1)

    module_name, attr = stages[stage]
    mod = __import__(module_name, fromlist=[attr])
    run_fn = getattr(mod, attr)
    run_fn(config)


if __name__ == "__main__":
    main()
