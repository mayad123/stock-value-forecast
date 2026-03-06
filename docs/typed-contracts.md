# Typed boundaries and data contracts

Key boundaries in the codebase use explicit types so contracts are clear and tooling can check them.

## Pipeline and artifact types (`src/types.py`)

- **RunRecord** – Shape of `run_record.json` produced by training. Used by `train/load.py` and serve for loading model and scaler, feature columns, ticker encoding.
- **ScalerDict** – Scaler (mean, scale) stored in run record; applied at inference.
- **FeatureManifest** – Shape of `feature_manifest.json` next to `features.csv` (split_boundaries, feature_columns, etc.).
- **ModelMetrics** – Per-model metrics dict (mse, rmse, mae, r2, directional_accuracy, ic, n_samples). Return type of `eval/metrics.compute_metrics`.
- **BacktestSummary** – Shape of the single-window backtest summary (dataset_version, models, n_test, …). Walk-forward returns a different artifact shape; use `Dict[str, Any]` where both are possible.
- **FeatureImportanceResult**, **FeatureImportanceItem** – Feature importance artifact and GET /feature_importance response.

All are **TypedDict** (total=False where keys are optional). Use them in type hints; at runtime they are plain dicts.

## Config section types (`src/config/models.py`)

- **PathsConfig**, **TimeHorizonConfig**, **TrainingConfig**, **EvalConfig** – TypedDicts for config sections. Use with `config.get("paths", {})` etc. for IDE and documentation.

## API request/response (`src/serve/schemas.py`)

All HTTP boundaries use **Pydantic** models:

- **PredictRequest**, **PredictResponse** – /predict
- **ModelInfoResponse** – /model_info
- **PredictionOptionsResponse** – /prediction_options
- **FeatureImportanceResponse**, **FeatureImportanceItemResponse** – /feature_importance

Responses are validated and serialized by FastAPI; request bodies are validated on input.

## Where to use types

- **Function signatures** – Use `RunRecord`, `ModelMetrics`, `FeatureImportanceResult` etc. in return types and arguments where the value is one of these shapes.
- **New code** – Prefer typing the boundary (config section, run record, API payload) rather than `Dict[str, Any]` when the shape is fixed.
- **Internal helpers** – No need to type every small dict; focus on boundaries (config in/out, artifact in/out, API in/out).
