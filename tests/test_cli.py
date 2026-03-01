"""Test that CLI stages run and produce structured output (stub)."""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_run_ingest_stub():
    """Without ALPHAVANTAGE_API_KEY, ingest fails with clear message."""
    result = subprocess.run(
        [sys.executable, "run.py", "ingest"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={k: v for k, v in __import__("os").environ.items() if k != "ALPHAVANTAGE_API_KEY"},
    )
    assert result.returncode == 1
    assert "[INGEST]" in result.stdout
    assert "API key" in result.stdout or "ALPHAVANTAGE" in result.stdout


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
    assert "[BACKTEST]" in result.stdout
    # Exit 0 if processed data exists; 1 if no processed dataset
    if result.returncode != 0:
        assert "Fatal" in result.stdout or "not found" in result.stdout.lower()


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
