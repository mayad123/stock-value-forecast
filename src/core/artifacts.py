"""
Centralized artifact and path resolution for models, reports, and processed data.

All path joins, "latest run" lookup, dataset version resolution, and deploy_artifacts
fallback live here. Training, evaluation, and serving use these helpers so behavior
is consistent and testable.

Resolution order (where applicable):
  - Explicit env override (e.g. SERVE_MODELS_PATH, MODEL_RUN_ID)
  - Config-derived path (from core.paths.get_paths)
  - deploy_artifacts/ fallback when primary is missing or empty
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple


def _has_model_dir(d: Path) -> bool:
    """True if directory contains a loadable model and run_record."""
    return (
        d.is_dir()
        and ((d / "model.keras").exists() or (d / "saved_model").exists())
        and (d / "run_record.json").exists()
    )


def resolve_run_dir(
    models_path: Path,
    dataset_version: Optional[str] = None,
    run_id_hint: Optional[str] = None,
    env_run_id: Optional[str] = None,
) -> Path:
    """
    Resolve the model run directory: explicit run_id (env or hint) or latest.

    Lookup order:
      1. env_run_id (e.g. from MODEL_RUN_ID) if given and valid
      2. run_id_hint (e.g. from config eval.tensorflow_run_id) if given and valid
      3. Latest directory under models_path: if dataset_version is set, only dirs whose
         name starts with dataset_version + "_"; else any valid run dir (e.g. for serve).

    Returns:
        Path to the run directory.
    Raises:
        FileNotFoundError if no valid run found.
    """
    run_id = (env_run_id or "").strip() or (run_id_hint or "").strip() or None
    if run_id:
        run_dir = models_path / run_id
        if run_dir.is_dir() and _has_model_dir(run_dir):
            return run_dir
        if env_run_id:
            raise FileNotFoundError(
                f"MODEL_RUN_ID run not found: {run_id}. "
                f"Check that the run exists under {models_path} or set MODEL_RUN_ID to a valid run dir name."
            )
        # hint invalid; fall through to latest

    if not models_path.exists():
        raise FileNotFoundError(
            f"Models dir not found: {models_path}. "
            "Run: python run.py train (or set SERVE_MODELS_PATH for serve)."
        )

    if dataset_version:
        candidates = [
            d
            for d in models_path.iterdir()
            if d.is_dir()
            and d.name.startswith(dataset_version + "_")
            and _has_model_dir(d)
        ]
        if not candidates:
            raise FileNotFoundError(
                f"No trained model for version '{dataset_version}' in {models_path}. "
                f"Run: python run.py train (with processed data for that version)."
            )
    else:
        candidates = [d for d in models_path.iterdir() if _has_model_dir(d)]
        if not candidates:
            raise FileNotFoundError(
                f"No trained model found in {models_path}. "
                "Run: python run.py train (or set SERVE_MODELS_PATH)."
            )
    return sorted(candidates)[-1]


@dataclass(frozen=True)
class ResolvedRun:
    """Result of resolving a model run: run_id and path to run directory."""

    run_id: str
    run_dir: Path


def resolve_run(
    models_path: Path,
    dataset_version: Optional[str] = None,
    run_id_hint: Optional[str] = None,
    env_run_id: Optional[str] = None,
) -> ResolvedRun:
    """Resolve run directory and return a small record (run_id, run_dir)."""
    run_dir = resolve_run_dir(
        models_path,
        dataset_version=dataset_version,
        run_id_hint=run_id_hint,
        env_run_id=env_run_id,
    )
    return ResolvedRun(run_id=run_dir.name, run_dir=run_dir)


def resolve_features_path(
    processed_path: Path,
    dataset_version: str,
    repo_root: Path,
) -> Path:
    """
    Resolve path to features.csv with deploy_artifacts fallbacks.

    Tries in order:
      1. processed_path / dataset_version / features.csv
      2. deploy_artifacts/processed / dataset_version / features.csv
      3. deploy_artifacts/processed / demo / features.csv

    Returns the first path that exists, or the primary path (caller may check exists()).
    """
    primary = processed_path / dataset_version / "features.csv"
    if primary.exists():
        return primary
    fallback_version = repo_root / "deploy_artifacts" / "processed" / dataset_version / "features.csv"
    if fallback_version.exists():
        return fallback_version
    fallback_demo = repo_root / "deploy_artifacts" / "processed" / "demo" / "features.csv"
    if fallback_demo.exists():
        return fallback_demo
    return primary


def resolve_report_path(
    reports_path: Path,
    filename: str,
    repo_root: Path,
) -> Path:
    """
    Resolve path to a report file (e.g. latest_metrics.json), with deploy_artifacts fallback.

    Tries reports_path/filename then deploy_artifacts/reports/filename.
    Returns the path to use (may not exist).
    """
    primary = reports_path / filename
    if primary.exists():
        return primary
    fallback = repo_root / "deploy_artifacts" / "reports" / filename
    if fallback.exists():
        return fallback
    return primary


def resolve_models_and_processed_for_serve(
    models_path: Path,
    processed_path: Path,
    repo_root: Path,
    env_models: Optional[str] = None,
    env_processed: Optional[str] = None,
) -> Tuple[Path, Path]:
    """
    Resolve models and processed paths for the serve layer, with env overrides and deploy fallback.

    Order:
      1. If env_models (SERVE_MODELS_PATH): use it for models_path.
      2. Else if primary models_path missing or has no valid run: try deploy_artifacts/models;
         if it has a valid run, use it and set processed_path to deploy_artifacts/processed when present.
      3. If env_processed (SERVE_PROCESSED_PATH): use it for processed_path.
      4. Else if processed_path does not exist and deploy_artifacts/processed exists: use it.

    Returns:
        (models_path, processed_path) to use for loading model and features.
    """
    if env_models and env_models.strip():
        models_path = Path(env_models).resolve()
    else:
        primary_has_run = (
            models_path.exists()
            and any(_has_model_dir(d) for d in models_path.iterdir() if d.is_dir())
        )
        if not primary_has_run:
            fallback_models = repo_root / "deploy_artifacts" / "models"
            fallback_processed = repo_root / "deploy_artifacts" / "processed"
            if fallback_models.exists() and any(
                _has_model_dir(d) for d in fallback_models.iterdir() if d.is_dir()
            ):
                models_path = fallback_models
                if fallback_processed.exists():
                    processed_path = fallback_processed

    if env_processed and env_processed.strip():
        processed_path = Path(env_processed).resolve()
    elif not processed_path.exists():
        deploy_processed = repo_root / "deploy_artifacts" / "processed"
        if deploy_processed.exists():
            processed_path = deploy_processed

    return models_path, processed_path


def run_id_from_version(dataset_version: str) -> str:
    """Generate a new run_id for a training run (timestamp-based, stable format)."""
    return f"{dataset_version}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def deploy_artifacts_models_path(repo_root: Path) -> Path:
    """Path to deploy_artifacts/models for mirroring trained runs (e.g. cloud deploy)."""
    return repo_root / "deploy_artifacts" / "models"


def deploy_artifacts_reports_path(repo_root: Path) -> Path:
    """Path to deploy_artifacts/reports for fallback report reads."""
    return repo_root / "deploy_artifacts" / "reports"
