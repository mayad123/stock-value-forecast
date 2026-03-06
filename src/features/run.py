"""Features stage: build deterministic feature matrix from raw prices."""

import sys

from src._cli import stage_done, stage_log
from src.features.service import build_features
from src.features.split import LeakageError, TimeOrderingError


def run(config: dict) -> None:
    """CLI entry: run feature build service; exit with clear message on failure."""
    stage_log("build-features", "Loading config")
    fw = config.get("feature_windows", {})
    stage_log("build-features", f"Feature windows: {fw}")

    try:
        build_features(config, log=lambda msg: stage_log("build-features", msg))
    except FileNotFoundError as e:
        stage_log("build-features", f"Fatal: {e}")
        sys.exit(1)
    except (TimeOrderingError, LeakageError) as e:
        stage_log("build-features", f"Fatal: {e}")
        sys.exit(1)

    if config.get("use_news"):
        stage_log("build-features", "News features not yet implemented (stub)")
    stage_done("build-features")
