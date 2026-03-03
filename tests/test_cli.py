"""Test that CLI stages run and produce structured output (stub)."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_run_ingest_stub():
    """With default config (recruiter_demo), ingest aborts immediately with clear message; no HTTP requests."""
    result = subprocess.run(
        [sys.executable, "run.py", "ingest"],
        cwd=REPO_ROOT,
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


def test_run_build_features_stub():
    result = subprocess.run(
        [sys.executable, "run.py", "build-features"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert "[BUILD-FEATURES]" in result.stdout
    # Exit 0 if processed data exists; 1 if raw data/manifests missing
    if result.returncode != 0:
        assert "Fatal" in result.stdout or "manifests" in result.stdout.lower()


def test_run_train_stub():
    pytest.importorskip("tensorflow")
    result = subprocess.run(
        [sys.executable, "run.py", "train"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert "[TRAIN]" in result.stdout
    if result.returncode != 0:
        assert "Fatal" in result.stdout or "not found" in result.stdout.lower() or "No training data" in result.stderr


def test_run_backtest_stub():
    result = subprocess.run(
        [sys.executable, "run.py", "backtest"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    out = result.stdout + result.stderr
    assert "[BACKTEST]" in result.stdout
    # Exit 0 if processed data exists; 1 if no processed dataset or error
    if result.returncode != 0:
        assert "Fatal" in out or "not found" in out.lower() or "Error" in out


def test_run_serve_stub():
    env = {k: v for k, v in __import__("os").environ.items()}
    env["SERVE_DRY_RUN"] = "1"
    result = subprocess.run(
        [sys.executable, "run.py", "serve"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
    assert "[SERVE]" in result.stdout


def test_run_unknown_stage_exits_nonzero():
    result = subprocess.run(
        [sys.executable, "run.py", "unknown"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Usage" in result.stdout or "Usage" in result.stderr


def test_run_demo_never_runs_ingest():
    """make demo / run.py demo must never trigger ingestion stages."""
    import run
    assert "ingest" not in run.RUN_DEMO_STAGES
    assert run.RUN_DEMO_STAGES == ("build-features", "train", "backtest")


def test_live_workflow_runs_ingest_first():
    """make live / run.py live must run ingest before build-features."""
    import run
    assert run.RUN_LIVE_STAGES[0] == "ingest"
    assert "ingest" in run.RUN_LIVE_STAGES
    idx_ingest = run.RUN_LIVE_STAGES.index("ingest")
    idx_build = run.RUN_LIVE_STAGES.index("build-features")
    assert idx_ingest < idx_build


def test_demo_mode_ingest_aborts_no_http():
    """In demo mode, ingest stage aborts immediately without making any HTTP requests."""
    from src.ingest.run import run as run_ingest
    from src._cli import load_config

    config = load_config(str(REPO_ROOT / "configs" / "recruiter_demo_real.yaml"))
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


def test_config_hash_from_file():
    """Config hash from file hashes exact file content."""
    from src._cli import config_hash_from_file

    path = REPO_ROOT / "configs" / "recruiter_demo_real.yaml"
    if not path.exists():
        pytest.skip("configs/recruiter_demo_real.yaml not found")
    h = config_hash_from_file(path)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_get_git_commit():
    """Git commit returns hex hash or None."""
    from src._cli import get_git_commit

    out = get_git_commit(REPO_ROOT)
    if out is not None:
        assert len(out) >= 7
        assert all(c in "0123456789abcdef" for c in out)
    # Call with nonexistent dir: should not raise, return None
    assert get_git_commit(Path("/nonexistent_repo_xyz")) is None
