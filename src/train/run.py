"""Train stage: load processed data, train TF model, save artifact and run record."""

import sys

from src._cli import stage_done, stage_log
from src.train.service import train


def run(config: dict) -> None:
    """CLI entry: run training service; exit with clear message on failure."""
    stage_log("train", "Loading config")
    hp = config.get("training", {})
    stage_log("train", f"Hyperparameters: epochs={hp.get('epochs')}, batch_size={hp.get('batch_size')}")

    try:
        version_hint = config.get("train", {}).get("processed_version", "latest")
        train(
            config,
            dataset_version_hint=version_hint,
            log=lambda msg: stage_log("train", msg),
        )
    except FileNotFoundError as e:
        stage_log("train", f"Fatal: {e}")
        sys.exit(1)
    except ValueError as e:
        stage_log("train", f"Fatal: {e}")
        sys.exit(1)
    stage_done("train")
