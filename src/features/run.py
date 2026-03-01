"""Features stage: build deterministic feature matrix from raw prices."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def run(config: dict) -> None:
    """Run the build-features pipeline: raw normalized prices -> processed features + manifest."""
    from src._cli import stage_log, stage_done
    from src.features.price_features import run_build_features

    stage_log("build-features", "Loading config")
    fw = config.get("feature_windows", {})
    stage_log("build-features", f"Feature windows: {fw}")

    try:
        from src.features.split import LeakageError, TimeOrderingError
        run_build_features(config, log=lambda msg: stage_log("build-features", msg))
    except FileNotFoundError as e:
        stage_log("build-features", f"Fatal: {e}")
        sys.exit(1)
    except (TimeOrderingError, LeakageError) as e:
        stage_log("build-features", f"Fatal: {e}")
        sys.exit(1)

    if config.get("use_news"):
        stage_log("build-features", "News features not yet implemented (stub)")
    stage_done("build-features")
