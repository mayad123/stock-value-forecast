"""
CLI entrypoint: parse args, dispatch to workflows or single stages.

Orchestration only—no business logic. Stage implementations live in
src.ingest, src.features, src.train, src.eval, src.serve; they are invoked
via run_stage() so they can be called from CLI, tests, or automation.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.config import load_config, require_live_apis_keys, validate_config
from src.config.validation import ConfigError
from src.core.paths import repo_root
from src.logging_config import get_logger

from src.orchestration.workflows import (
    DEMO_CONFIG,
    DEMO_REAL_CONFIG,
    LIVE_CONFIG,
    run_demo,
    run_demo_real,
    run_live,
)

# Stage name -> (module, attr) for dynamic dispatch. Ingest/features/train/eval use run.py which delegates to service.
STAGES: Dict[str, Tuple[str, str]] = {
    "ingest": ("src.ingest", "run_ingest"),
    "build-features": ("src.features", "run_build_features"),
    "train": ("src.train", "run_train"),
    "backtest": ("src.eval", "run_backtest"),
    "feature-importance": ("src.eval.service", "feature_importance"),
    "serve": ("src.serve", "run_serve"),
}
WORKFLOWS = ("demo", "demo-real", "live")


def run_stage(stage_name: str, config: Dict[str, Any]) -> None:
    """
    Run a single pipeline stage by name. Use from CLI, tests, or automation.

    Args:
        stage_name: One of STAGES keys (e.g. "ingest", "build-features", "backtest").
        config: Loaded config dict (must have _config_path if stage needs it).
    """
    if stage_name not in STAGES:
        raise ValueError(f"Unknown stage: {stage_name}. Valid: {list(STAGES)}")
    module_name, attr = STAGES[stage_name]
    mod = __import__(module_name, fromlist=[attr])
    getattr(mod, attr)(config)


def _parse_args(argv: List[str]) -> Tuple[Optional[str], Optional[str], List[str], Optional[str]]:
    """Return (config_path_or_none, stage, rest_positionals, dataset_version_or_none)."""
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
    print("  ingest | build-features | train | backtest | serve | feature-importance | manifest [VERSION] | build-manifest | validate-prices [VERSION]")
    print("")
    print("Examples:")
    print("  make demo          # or: python run.py demo")
    print("  make live         # or: python run.py live")
    print("  python run.py --config configs/live_apis.yaml ingest")
    print("  python run.py manifest demo      # regenerate data/sample/manifests/demo.json from CSVs")
    print("  python run.py build-manifest --dataset-version demo_real_v1   # generate data/sample/manifests/demo_real_v1.json from all CSVs")
    print("  python run.py validate-prices demo   # validate prices_normalized CSVs, write reports/data_validation_demo.json")
    print("  python run.py demo-real             # full pipeline on real data; to avoid TF locking use: make demo-real or ./scripts/run-demo-real.sh")


def _load_config_for_stage(config_path_arg: Optional[str], default_path: Path) -> Dict[str, Any]:
    """Load config from path or default; set _config_path; validate and fail early if invalid."""
    if config_path_arg:
        p = Path(config_path_arg)
        if not p.is_absolute():
            p = repo_root() / p
        config = load_config(str(p))
        config["_config_path"] = str(p.resolve())
    else:
        config = load_config(str(default_path))
        config["_config_path"] = str(default_path.resolve())
    try:
        validate_config(config, require_mode=False)
    except ConfigError as e:
        get_logger("cli").error("Config error: %s", e)
        sys.exit(1)
    return config


def _run_manifest(config_path_arg: Optional[str], rest_args: List[str]) -> None:
    """Manifest [VERSION]: regenerate manifest from prices_normalized/."""
    config = _load_config_for_stage(config_path_arg, repo_root() / DEMO_CONFIG)
    raw = config.get("paths", {}).get("data_raw", "data/sample")
    raw_root = repo_root() / raw if not Path(raw).is_absolute() else Path(raw)
    version = rest_args[0] if rest_args else config.get("feature_build", {}).get("raw_dataset_version", "demo")
    from src.data.manifest import generate_manifest
    try:
        generate_manifest(raw_root, version)
    except (FileNotFoundError, ValueError) as e:
        get_logger("cli").error("Manifest: %s", e)
        sys.exit(1)


def _run_validate_prices(config_path_arg: Optional[str], rest_args: List[str]) -> None:
    """Validate-prices [VERSION]: validate CSVs, optional auto-fix, write report."""
    config = _load_config_for_stage(config_path_arg, repo_root() / DEMO_CONFIG)
    raw = config.get("paths", {}).get("data_raw", "data/sample")
    raw_root = repo_root() / raw if not Path(raw).is_absolute() else Path(raw)
    version = rest_args[0] if rest_args else config.get("feature_build", {}).get("raw_dataset_version", "demo")
    from src.data.validate_prices_csv import run_validate_prices, ValidationError
    try:
        run_validate_prices(config, raw_root=raw_root, dataset_version=version)
    except ValidationError as e:
        get_logger("cli").error("Validate-prices: %s", e)
        sys.exit(1)


def _run_build_manifest(config_path_arg: Optional[str], rest_args: List[str], dataset_version_arg: Optional[str]) -> None:
    """Build-manifest: requires --dataset-version; generate manifests/<version>.json."""
    version = dataset_version_arg
    if not version and len(rest_args) >= 2 and rest_args[0] == "--dataset-version":
        version = rest_args[1]
    elif not version and rest_args and not rest_args[0].startswith("-"):
        version = rest_args[0]
    if not version:
        get_logger("cli").error(
            "build-manifest requires --dataset-version (e.g. python run.py build-manifest --dataset-version demo_real_v1)"
        )
        sys.exit(1)
    config = _load_config_for_stage(config_path_arg, repo_root() / DEMO_CONFIG)
    from src.data.build_manifest import run_build_manifest
    try:
        run_build_manifest(config, dataset_version=version)
    except (FileNotFoundError, ValueError) as e:
        get_logger("cli").error("Build-manifest: %s", e)
        sys.exit(1)


def _preflight_demo_prices(config: Dict[str, Any]) -> None:
    """Run validate-prices before build-features/train/backtest in demo mode (skip if train subprocess)."""
    if os.environ.get("RUN_TRAIN_SUBPROCESS") == "1":
        return
    from src.data.validate_prices_csv import run_validate_prices, ValidationError
    try:
        run_validate_prices(config)
    except ValidationError as e:
        msg = str(e)
        if "Prices directory not found" in msg:
            get_logger("cli").warning("Validate-prices (warning only): %s", msg)
        else:
            get_logger("cli").error("Validate-prices: %s", msg)
            sys.exit(1)


def run_cli(argv: List[str]) -> None:
    """
    Parse argv and run the requested workflow or stage. Entry point for run.py.

    Handles: help, manifest, validate-prices, build-manifest, demo, demo-real,
    live, or a single stage (with optional preflight for demo mode).
    """
    config_path_arg, stage, rest_args, dataset_version_arg = _parse_args(argv)

    if stage == "help":
        _print_help()
        sys.exit(0)

    if stage == "manifest":
        _run_manifest(config_path_arg, rest_args)
        return

    if stage == "validate-prices":
        _run_validate_prices(config_path_arg, rest_args)
        return

    if stage == "build-manifest":
        _run_build_manifest(config_path_arg, rest_args, dataset_version_arg)
        return

    if stage is None or (stage not in STAGES and stage not in WORKFLOWS):
        _print_help()
        sys.exit(1)

    # Workflows: load, validate (including mode), then run
    def _validate_workflow_config(config: Dict[str, Any], expected_mode: str, workflow_name: str) -> None:
        try:
            validate_config(config, require_mode=True)
        except ConfigError as e:
            get_logger("cli").error("Config error: %s", e)
            sys.exit(1)
        if config.get("mode") != expected_mode:
            get_logger("cli").error("%s must use config with mode: %s", workflow_name, expected_mode)
            sys.exit(1)

    if stage == "demo":
        demo_path = repo_root() / DEMO_CONFIG
        config = load_config(str(demo_path))
        config["_config_path"] = str(demo_path.resolve())
        _validate_workflow_config(config, "recruiter_demo", "demo")
        run_demo(config, STAGES, str(demo_path))
        return

    if stage == "demo-real":
        demo_real_path = repo_root() / DEMO_REAL_CONFIG
        if not demo_real_path.exists():
            get_logger("cli").error("Config not found: %s", demo_real_path)
            sys.exit(1)
        config = load_config(str(demo_real_path))
        config["_config_path"] = str(demo_real_path.resolve())
        _validate_workflow_config(config, "recruiter_demo", "demo-real")
        run_demo_real(config, STAGES, str(demo_real_path))
        return

    if stage == "live":
        live_path = repo_root() / LIVE_CONFIG
        config = load_config(str(live_path))
        config["_config_path"] = str(live_path.resolve())
        _validate_workflow_config(config, "live_apis", "live")
        run_live(config, STAGES, str(live_path))
        return

    # Single stage
    config = _load_config_for_stage(config_path_arg, repo_root() / DEMO_CONFIG)
    if config.get("mode") == "live_apis":
        require_live_apis_keys(config)

    if stage in ("build-features", "train", "backtest") and config.get("mode") == "recruiter_demo":
        _preflight_demo_prices(config)

    run_stage(stage, config)
