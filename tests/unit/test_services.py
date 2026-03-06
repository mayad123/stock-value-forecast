"""Tests that domain services are callable with explicit inputs and have clear contracts."""

import pytest

from src.config import load_config


def test_ingest_service_raises_on_demo_mode(project_root):
    """Ingest service raises ValueError in demo mode (no sys.exit from service)."""
    from src.ingest.service import run_ingest

    config = load_config(str(project_root / "configs/recruiter_demo_real.yaml"))
    assert config.get("mode") == "recruiter_demo"
    with pytest.raises(ValueError, match="Demo mode"):
        run_ingest(config)


def test_features_service_build_features_signature():
    """Features service exposes build_features(config, *, raw_root=..., processed_root=..., log=...) -> str."""
    from src.features.service import build_features

    # Signature is callable with config only (optional kwargs have defaults)
    config = {"paths": {}, "feature_windows": {}, "time_horizon": {}, "feature_build": {}, "tickers": {"symbols": []}}
    # Will fail on missing data; we only check it's callable and raises a known type
    with pytest.raises((FileNotFoundError, KeyError, ValueError)):
        build_features(config)


def test_train_service_train_signature():
    """Train service exposes train(config, *, processed_root=..., models_root=..., ...) -> str."""
    pytest.importorskip("tensorflow")
    from src.train.service import train

    config = load_config(None)
    config["paths"] = {"data_processed": "/nonexistent", "models": "/nonexistent"}
    with pytest.raises((FileNotFoundError, ValueError)):
        train(config)


def test_eval_service_backtest_signature():
    """Eval service exposes backtest(config, *, ...) -> dict and feature_importance(config, *) -> dict."""
    from src.eval.service import backtest, feature_importance

    config = load_config(None)
    config["paths"] = {"data_processed": "/nonexistent", "models": "/nonexistent", "reports": "/tmp"}
    with pytest.raises(FileNotFoundError):
        backtest(config)
    with pytest.raises(FileNotFoundError):
        feature_importance(config)
