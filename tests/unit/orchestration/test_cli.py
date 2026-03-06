"""Test that CLI stages run and produce structured output (stub)."""

import subprocess
import sys
from pathlib import Path

import pytest


def test_run_ingest_stub(project_root):
    """With default config (recruiter_demo), ingest aborts immediately with clear message; no HTTP requests."""
    result = subprocess.run(
        [sys.executable, "run.py", "ingest"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    out = result.stdout + result.stderr
    assert "Demo mode" in out or "sample data" in out
    assert "live_apis" in out


def test_live_apis_require_live_apis_keys_exits_when_keys_missing():
    """With mode live_apis and no API keys in env, require_live_apis_keys exits with clear message."""
    import os
    from src._cli import require_live_apis_keys

    env = os.environ
    saved_av = env.pop("ALPHAVANTAGE_API_KEY", None)
    saved_mx = env.pop("MARKETAUX_API_KEY", None)
    try:
        with pytest.raises(SystemExit) as exc_info:
            require_live_apis_keys({"mode": "live_apis", "use_news": False})
        assert exc_info.value.code == 1

        # When use_news is true and MARKETAUX is missing, should also exit
        with pytest.raises(SystemExit):
            require_live_apis_keys({"mode": "live_apis", "use_news": True})
    finally:
        if saved_av is not None:
            env["ALPHAVANTAGE_API_KEY"] = saved_av
        if saved_mx is not None:
            env["MARKETAUX_API_KEY"] = saved_mx


def test_run_build_features_stub(project_root):
    result = subprocess.run(
        [sys.executable, "run.py", "build-features"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    out = result.stdout + result.stderr
    assert "[BUILD-FEATURES]" in out
    # Exit 0 if processed data exists; 1 if raw data/manifests missing
    if result.returncode != 0:
        assert "Fatal" in out or "manifests" in out.lower()


def test_run_train_stub(project_root):
    pytest.importorskip("tensorflow")
    result = subprocess.run(
        [sys.executable, "run.py", "train"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    out = result.stdout + result.stderr
    assert "[TRAIN]" in out
    if result.returncode != 0:
        assert "Fatal" in out or "not found" in out.lower() or "No training data" in out


def test_run_backtest_stub(project_root):
    result = subprocess.run(
        [sys.executable, "run.py", "backtest"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    out = result.stdout + result.stderr
    assert "[BACKTEST]" in out
    # Exit 0 if processed data exists; 1 if no processed dataset or error
    if result.returncode != 0:
        assert "Fatal" in out or "not found" in out.lower() or "Error" in out


def test_run_serve_stub(project_root):
    env = {k: v for k, v in __import__("os").environ.items()}
    env["SERVE_DRY_RUN"] = "1"
    result = subprocess.run(
        [sys.executable, "run.py", "serve"],
        cwd=project_root,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "[SERVE]" in (result.stdout + result.stderr)


def test_run_unknown_stage_exits_nonzero(project_root):
    result = subprocess.run(
        [sys.executable, "run.py", "unknown"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Usage" in result.stdout or "Usage" in result.stderr


def test_run_stage_programmatic():
    """Stages can be invoked via orchestration.run_stage without going through CLI."""
    from src.orchestration import run_stage

    with pytest.raises(ValueError, match="Unknown stage"):
        run_stage("not-a-stage", {})

    # Registry exposes expected stages (programmatic entry points)
    from src.orchestration.entrypoint import STAGES
    assert "ingest" in STAGES
    assert "build-features" in STAGES
    assert "backtest" in STAGES
    assert "serve" in STAGES


def test_run_demo_never_runs_ingest():
    """make demo / run.py demo must never trigger ingestion stages."""
    from src.orchestration.workflows import RUN_DEMO_STAGES
    assert "ingest" not in RUN_DEMO_STAGES
    assert RUN_DEMO_STAGES == ("build-features", "train", "backtest")


def test_live_workflow_runs_ingest_first():
    """make live / run.py live must run ingest before build-features."""
    from src.orchestration.workflows import RUN_LIVE_STAGES
    assert RUN_LIVE_STAGES[0] == "ingest"
    assert "ingest" in RUN_LIVE_STAGES
    idx_ingest = RUN_LIVE_STAGES.index("ingest")
    idx_build = RUN_LIVE_STAGES.index("build-features")
    assert idx_ingest < idx_build


def test_demo_mode_ingest_aborts_no_http(project_root):
    """In demo mode, ingest stage aborts immediately without making any HTTP requests."""
    from src.ingest.run import run as run_ingest
    from src._cli import load_config

    config = load_config(str(project_root / "configs" / "recruiter_demo_real.yaml"))
    assert config.get("mode") == "recruiter_demo"
    with pytest.raises(SystemExit) as exc_info:
        run_ingest(config)
    assert exc_info.value.code == 1


def test_live_mode_build_features_fails_clearly_when_data_missing():
    """In live mode, feature building fails with clear message if normalized dataset is missing."""
    import tempfile
    from src.features.price_features import run_build_features

    with tempfile.TemporaryDirectory() as tmp:
        raw_root = Path(tmp)  # empty; no manifests
        config = {
            "mode": "live_apis",
            "paths": {"data_raw": str(raw_root), "data_processed": str(Path(tmp) / "processed")},
            "feature_build": {"raw_dataset_version": "latest"},
            "feature_windows": {"lookback_days": 21, "forward_return_days": 1},
            "time_horizon": {},
        }
        with pytest.raises(FileNotFoundError) as exc_info:
            run_build_features(config, raw_root=raw_root)
    assert "Live mode" in str(exc_info.value) or "Run ingest" in str(exc_info.value)


def test_config_hash_from_dict_stable():
    """Config hash from dict is deterministic and excludes _config_path."""
    from src._cli import config_hash_from_dict

    cfg = {"a": 1, "b": 2, "training": {"epochs": 3}}
    h1 = config_hash_from_dict(cfg)
    h2 = config_hash_from_dict(cfg)
    assert h1 == h2
    assert len(h1) == 64
    assert all(c in "0123456789abcdef" for c in h1)

    cfg["_config_path"] = "/some/path.yaml"
    h3 = config_hash_from_dict(cfg)
    assert h3 == h1  # internal key excluded from hash


def test_config_hash_from_file(project_root):
    """Config hash from file hashes exact file content."""
    from src._cli import config_hash_from_file

    path = project_root / "configs" / "recruiter_demo_real.yaml"
    if not path.exists():
        pytest.skip("configs/recruiter_demo_real.yaml not found")
    h = config_hash_from_file(path)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_get_git_commit(project_root):
    """Git commit returns hex hash or None."""
    from src._cli import get_git_commit

    out = get_git_commit(project_root)
    if out is not None:
        assert len(out) >= 7
        assert all(c in "0123456789abcdef" for c in out)
    # Call with nonexistent dir: should not raise, return None
    assert get_git_commit(Path("/nonexistent_repo_xyz")) is None
