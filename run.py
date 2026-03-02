#!/usr/bin/env python3
"""
Single entry point for the ML pipeline.

Workflows (use these to avoid cross-mode accidents):
  demo   configs/recruiter_demo.yaml  build-features -> train -> backtest (no ingest, no API keys)
  live   configs/live_apis.yaml       ingest -> build-features -> train -> backtest (requires API keys)

Single stages (require --config unless using default): ingest | build-features | train | backtest | serve
  python run.py [--config CONFIG] <stage>

Loads .env from repo root if present (for ALPHAVANTAGE_API_KEY, MARKETAUX_API_KEY, etc.).
"""

import sys
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

DEMO_CONFIG = "configs/recruiter_demo.yaml"
LIVE_CONFIG = "configs/live_apis.yaml"

# Fixed stage order per workflow (demo never runs ingest; live runs ingest first)
RUN_DEMO_STAGES = ("build-features", "train", "backtest")
RUN_LIVE_STAGES = ("ingest", "build-features", "train", "backtest")


def _print_help() -> None:
    print("Usage: python run.py [--config CONFIG] <stage>")
    print("       python run.py demo | live")
    print("")
    print("Workflows (explicit mode; config is fixed, no cross-mode):")
    print("  demo   configs/recruiter_demo.yaml   build-features -> train -> backtest")
    print("         (offline, no ingest, no API keys)")
    print("  live   configs/live_apis.yaml        ingest -> build-features -> train -> backtest")
    print("         (ingest prices, optional news, then features/train/backtest; requires API keys)")
    print("")
    print("Single stages (use --config for live_apis; default config is recruiter_demo):")
    print("  ingest | build-features | train | backtest | serve")
    print("")
    print("Examples:")
    print("  make demo          # or: python run.py demo")
    print("  make live         # or: python run.py live")
    print("  python run.py --config configs/live_apis.yaml ingest")


def _parse_args(argv: list) -> tuple:
    """Return (config_path_or_none, stage). Supports --config CONFIG and -h/--help."""
    args = argv[1:]
    if "-h" in args or "--help" in args:
        return None, "help"
    config_path = None
    while args and args[0] == "--config" and len(args) >= 2:
        config_path = args[1]
        args = args[2:]
    if not args:
        return config_path, None
    return config_path, args[0]


def main() -> None:
    stages = {
        "ingest": ("src.ingest", "run_ingest"),
        "build-features": ("src.features", "run_build_features"),
        "train": ("src.train", "run_train"),
        "backtest": ("src.eval", "run_backtest"),
        "serve": ("src.serve", "run_serve"),
    }
    workflows = ("demo", "live")

    config_path_arg, stage = _parse_args(sys.argv)
    if stage == "help":
        _print_help()
        sys.exit(0)
    if stage is None or (stage not in stages and stage not in workflows):
        _print_help()
        sys.exit(1)

    from src._cli import load_config, require_live_apis_keys

    # Workflows: fix config by mode to prevent cross-mode
    if stage == "demo":
        config = load_config(str(REPO_ROOT / DEMO_CONFIG))
        if config.get("mode") != "recruiter_demo":
            print("Error: demo must use config with mode: recruiter_demo", file=sys.stderr)
            sys.exit(1)
        for s in RUN_DEMO_STAGES:
            module_name, attr = stages[s]
            mod = __import__(module_name, fromlist=[attr])
            getattr(mod, attr)(config)
        return

    if stage == "live":
        config = load_config(str(REPO_ROOT / LIVE_CONFIG))
        if config.get("mode") != "live_apis":
            print("Error: live must use config with mode: live_apis", file=sys.stderr)
            sys.exit(1)
        require_live_apis_keys(config)
        for s in RUN_LIVE_STAGES:
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
    else:
        config = load_config(str(REPO_ROOT / DEMO_CONFIG))

    if config.get("mode") == "live_apis":
        require_live_apis_keys(config)

    module_name, attr = stages[stage]
    mod = __import__(module_name, fromlist=[attr])
    run_fn = getattr(mod, attr)
    run_fn(config)


if __name__ == "__main__":
    main()
