"""Train stage: load processed data, train TF model, save artifact and run record."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def run(config: dict) -> None:
    """Run training: processed data -> train/val -> SavedModel + run record."""
    from src._cli import stage_log, stage_done
    from src.train.train import run_training

    stage_log("train", "Loading config")
    hp = config.get("training", {})
    stage_log("train", f"Hyperparameters: epochs={hp.get('epochs')}, batch_size={hp.get('batch_size')}")

    try:
        version_hint = config.get("train", {}).get("processed_version", "latest")
        run_training(config, dataset_version_hint=version_hint, log=lambda msg: stage_log("train", msg))
    except FileNotFoundError as e:
        stage_log("train", f"Fatal: {e}")
        sys.exit(1)
    except ValueError as e:
        stage_log("train", f"Fatal: {e}")
        sys.exit(1)

    stage_done("train")
