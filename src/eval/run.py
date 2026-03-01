"""Eval stage: backtest baselines and model on test window, write metrics summary."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def run(config: dict) -> None:
    """Run backtest: evaluate all baselines on test split, produce single metrics summary artifact."""
    from src._cli import stage_log, stage_done
    from src.eval.backtest import run_backtest

    stage_log("backtest", "Loading config")
    version_hint = config.get("eval", {}).get("processed_version", "latest")
    stage_log("backtest", f"Processed version: {version_hint}")

    try:
        run_backtest(config, dataset_version_hint=version_hint, log=lambda msg: stage_log("backtest", msg))
    except FileNotFoundError as e:
        stage_log("backtest", f"Fatal: {e}")
        sys.exit(1)

    stage_done("backtest")
