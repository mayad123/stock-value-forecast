"""
Model and artifact loading for the serve layer.

Single entry point: load_artifacts(repo_root, overrides) -> ServeContext.
Startup calls this once; routes use the returned context.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from src.core.artifacts import (
    resolve_features_path,
    resolve_models_and_processed_for_serve,
    resolve_run_dir,
)
from src.logging_config import get_logger
from src.serve.state import ServeContext


def _compute_schema_fingerprint(feature_columns: list) -> str:
    """Stable identifier from feature column names and order."""
    blob = json.dumps(feature_columns, sort_keys=False)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def load_artifacts(
    repo_root: Path,
    *,
    models_path: Optional[Path] = None,
    processed_path: Optional[Path] = None,
    reports_path: Optional[Path] = None,
    sample_prices_path: Optional[Path] = None,
    env_models: Optional[str] = None,
    env_processed: Optional[str] = None,
    env_reports: Optional[str] = None,
    env_sample_prices: Optional[str] = None,
    env_run_id: Optional[str] = None,
) -> ServeContext:
    """
    Resolve paths, load model and run record, load features CSV, build serve context.
    Raises FileNotFoundError if model or run dir cannot be resolved.
    """
    log = get_logger("serve")
    log.info("Loading model and artifacts...")

    models_path = models_path or repo_root / "models"
    processed_path = processed_path or repo_root / "data" / "processed"
    reports_path = reports_path or repo_root / "reports"
    sample_prices_path = sample_prices_path or repo_root / "data" / "sample" / "prices_normalized"

    if env_reports and env_reports.strip():
        reports_path = Path(env_reports).resolve()
    if env_sample_prices and env_sample_prices.strip():
        sample_prices_path = Path(env_sample_prices).resolve()

    models_path, processed_path = resolve_models_and_processed_for_serve(
        models_path,
        processed_path,
        repo_root,
        env_models=env_models,
        env_processed=env_processed,
    )

    run_dir = resolve_run_dir(
        models_path,
        dataset_version=None,
        env_run_id=env_run_id,
    )
    run_id = run_dir.name
    log.info("Resolved run: %s", run_id)

    from src.train.load import load_trained_model

    model, run_record = load_trained_model(run_dir)
    run_record.setdefault("run_id", run_id)

    feature_columns = list(run_record.get("feature_columns", []))
    ticker_columns = list(run_record.get("ticker_columns", []))
    ticker_to_idx = dict(run_record.get("ticker_to_idx", {}))
    expected_dim = len(feature_columns)
    schema_fingerprint = _compute_schema_fingerprint(feature_columns)
    dataset_version = run_record.get("dataset_version", "")

    log.info("Model loaded: dataset_version=%s, features=%d", dataset_version, len(feature_columns))

    features_path = resolve_features_path(processed_path, dataset_version, repo_root)
    if features_path.exists():
        features_df = pd.read_csv(features_path)
        features_df["date"] = features_df["date"].astype(str)
        log.info("Features loaded: %d rows", len(features_df))
    else:
        features_df = pd.DataFrame()
        log.warning("Features file not found at %s; prediction options may be empty.", features_path)

    return ServeContext(
        model=model,
        run_record=run_record,
        run_id=run_id,
        features_df=features_df,
        feature_columns=feature_columns,
        ticker_columns=ticker_columns,
        ticker_to_idx=ticker_to_idx,
        expected_dim=expected_dim,
        schema_fingerprint=schema_fingerprint,
        reports_path=reports_path,
        sample_prices_path=sample_prices_path,
        repo_root=repo_root,
    )


def load_artifacts_from_env(repo_root: Path) -> ServeContext:
    """Load artifacts using paths and overrides from environment (get_serve_env_overrides)."""
    from src.config.secrets import get_serve_env_overrides

    overrides = get_serve_env_overrides()
    return load_artifacts(
        repo_root,
        env_models=overrides.get("SERVE_MODELS_PATH"),
        env_processed=overrides.get("SERVE_PROCESSED_PATH"),
        env_reports=overrides.get("SERVE_REPORTS_PATH"),
        env_sample_prices=overrides.get("SERVE_SAMPLE_PRICES_PATH"),
        env_run_id=overrides.get("MODEL_RUN_ID"),
    )
