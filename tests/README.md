# Test layout

Tests are organized to mirror the production-oriented structure.

## Structure

- **`unit/`** – Tests by domain; one subpackage per area.
  - **`config/`** – Config loading, validation, secrets.
  - **`core/`** – Paths, artifact resolution (`test_core.py`, `test_artifacts.py`).
  - **`data/`** – Manifest generation, price validation.
  - **`ingest/`** – Price and news ingestion (mocked API where needed).
  - **`features/`** – Feature building, split logic, sentiment.
  - **`train/`** – Training (skipped when TensorFlow is not installed).
  - **`eval/`** – Backtest, metrics, feature importance.
  - **`serve/`** – FastAPI app (health, model_info, predict, prediction_options, etc.).
  - **`orchestration/`** – CLI dispatch, workflows, stage stubs.
  - **`test_services.py`** – Domain service interfaces (ingest, features, train, eval).
  - **`test_types.py`** – Typed contracts (`src.types` smoke tests).
- **`integration/`** – Cross-domain and invariants.
  - **`test_leakage_invariants.py`** – Time ordering and leakage errors.
  - **`test_pipeline_timeseries.py`** – Split boundaries, ordering, leakage detection.
  - **`test_sample_integration.py`** – Build-features → train → load → inference on `data/sample/`.
- **`e2e/`** – End-to-end pipeline.
  - **`test_integration_e2e.py`** – Minimal pipeline (build-features → train → backtest) on temp data.

## Fixtures

- **`project_root`** (in `conftest.py`) – Project root path. Use for `cwd=`, config paths, or `data/sample`.
- **`REPO_ROOT`** – Same path, for use in module-level constants (e.g. skip conditions). Import with `from tests.conftest import REPO_ROOT`.

## Running tests

- All: `pytest tests/` or `make test` (if defined).
- By layer: `pytest tests/unit/`, `pytest tests/integration/`, `pytest tests/e2e/`.
- By domain: `pytest tests/unit/config/`, `pytest tests/unit/serve/`, etc.
