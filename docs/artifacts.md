# Artifact and path management

All model, report, and processed-data path resolution lives in `src.core.artifacts`. Training, evaluation, and serving use these helpers so behavior is consistent and testable.

## Responsibilities

- **Run directory resolution** – Resolve the model run dir by env `MODEL_RUN_ID`, config hint (`eval.tensorflow_run_id`), or latest run for a dataset version.
- **Features path** – Path to `features.csv` with fallbacks: `processed/<version>/`, then `deploy_artifacts/processed/<version>/`, then `deploy_artifacts/processed/demo/`.
- **Report paths** – Path to report files (e.g. `latest_metrics.json`) with fallback to `deploy_artifacts/reports/`.
- **Serve path resolution** – Resolve `models/` and `processed/` for the serve layer with env overrides and `deploy_artifacts/` fallback when primary is missing or empty.
- **Run ID generation** – `run_id_from_version(dataset_version)` for new training runs; `deploy_artifacts_models_path(repo_root)` for mirroring.

## Resolution order (serve)

1. Env overrides: `SERVE_MODELS_PATH`, `SERVE_PROCESSED_PATH`, `MODEL_RUN_ID`, etc. (see `src.config.secrets.get_serve_env_overrides()`).
2. Config-derived paths (from `core.paths.get_paths(config)`).
3. `deploy_artifacts/` fallback when primary models or processed dir is missing or has no valid run.

## Main APIs

| Function | Use |
|----------|-----|
| `resolve_run_dir(models_path, dataset_version, run_id_hint, env_run_id)` | Get run directory; pass `dataset_version=None` for “latest any version” (e.g. serve). |
| `resolve_run(...)` | Same as above but returns `ResolvedRun(run_id, run_dir)`. |
| `resolve_features_path(processed_path, dataset_version, repo_root)` | Path to `features.csv` with deploy fallbacks. |
| `resolve_report_path(reports_path, filename, repo_root)` | Path to a report file with deploy fallback. |
| `resolve_models_and_processed_for_serve(...)` | Apply env and deploy fallback for serve. |
| `run_id_from_version(dataset_version)` | New run ID for training. |
| `deploy_artifacts_models_path(repo_root)` | Path for mirroring trained runs to deploy. |

Processed dataset version resolution (e.g. “latest” → concrete version dir) stays in `src.data.versioning.resolve_processed_version`.
