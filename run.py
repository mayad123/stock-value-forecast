#!/usr/bin/env python3
"""
Single entry point for the ML pipeline.

Workflows (use these to avoid cross-mode accidents):
  demo   configs/recruiter_demo_real.yaml  build-features -> train -> backtest (no ingest, no API keys)
  live   configs/live_apis.yaml       ingest -> build-features -> train -> backtest (requires API keys)

Single stages (require --config unless using default): ingest | build-features | train | backtest | serve
  python run.py [--config CONFIG] <stage>

Loads .env from repo root if present (for ALPHAVANTAGE_API_KEY, MARKETAUX_API_KEY, etc.).

Orchestration (workflows, dispatch) lives in src.orchestration; this script only sets up
environment and delegates to run_cli().
"""
# Reduce TensorFlow hangs: CPU-only, single-thread, quiet C++ logs (must be before any TF import)
import os
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")       # avoid GPU init that can block before first epoch
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")      # 3 = errors only (suppress mutex.cc Lock blocking)
os.environ.setdefault("TF_NUM_INTEROP_THREADS", "1")   # fewer threads => less lock contention
os.environ.setdefault("TF_NUM_INTRAOP_THREADS", "1")   # fewer threads => less lock contention

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

from src.orchestration import run_cli


def main() -> None:
    run_cli(sys.argv)


if __name__ == "__main__":
    main()
