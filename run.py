#!/usr/bin/env python3
"""
Single entry point for the ML pipeline.
Usage: python run.py <stage>
Stages: ingest | build-features | train | backtest | serve
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


def main() -> None:
    stages = {
        "ingest": ("src.ingest", "run_ingest"),
        "build-features": ("src.features", "run_build_features"),
        "train": ("src.train", "run_train"),
        "backtest": ("src.eval", "run_backtest"),
        "serve": ("src.serve", "run_serve"),
    }

    if len(sys.argv) < 2 or sys.argv[1] not in stages:
        print("Usage: python run.py <stage>")
        print("Stages:", " | ".join(stages))
        sys.exit(1)

    stage = sys.argv[1]
    module_name, attr = stages[stage]

    from src._cli import load_config
    config_path = REPO_ROOT / "configs" / "default.yaml"
    config = load_config(str(config_path))

    mod = __import__(module_name, fromlist=[attr])
    run_fn = getattr(mod, attr)
    run_fn(config)


if __name__ == "__main__":
    main()
