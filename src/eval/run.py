"""Eval stage: backtest baselines and model on test window, write metrics summary."""

import sys

from src._cli import stage_done, stage_log
from src.eval.service import backtest


def run(config: dict) -> None:
    """CLI entry: run backtest service; exit with clear message on failure."""
    stage_log("backtest", "Loading config")
    version_hint = config.get("eval", {}).get("processed_version", "latest")
    stage_log("backtest", f"Processed version: {version_hint}")

    try:
        backtest(
            config,
            dataset_version_hint=version_hint,
            log=lambda msg: stage_log("backtest", msg),
        )
    except FileNotFoundError as e:
        stage_log("backtest", f"Fatal: {e}")
        sys.exit(1)
    stage_done("backtest")
