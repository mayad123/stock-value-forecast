# Stock Value Forecast

Machine-learning portfolio project demonstrating a small but production-shaped time-series forecasting pipeline: ingest → features → train → backtest → serve → UI.

---

## Live demo

**Streamlit UI (no setup required):**  
[https://stock-value-forecast-qneqzw3kpe5d69gjxmmete.streamlit.app/](https://stock-value-forecast-qneqzw3kpe5d69gjxmmete.streamlit.app/)

What you can see there:
- **Model Overview:** current trained run (version, dataset, feature schema fingerprint, metrics, baseline vs model comparison).
- **Prediction Explorer:** single-ticker predictions driven by the same features used at train time.
- **Fold Stability:** walk-forward folds with per-fold metrics and variability plots.

This is the best entry point for recruiters and hiring managers; you can get a feel for the system in under a minute.

---

## Architecture at a glance

End-to-end flow:

```text
AlphaVantage / sample CSVs
        │
        ▼
  Ingest (optional live mode)
        │
        ▼
  Feature build (price features, leakage checks)
        │
        ▼
  Train (TF/Keras model, run record)
        │
        ▼
  Backtest (baselines + model, metrics + reports)
        │
        ▼
  Serve API (FastAPI, /predict, /model_info)
        │
        ▼
  Streamlit UI (this repo’s frontend/)
```

Key pieces:
- **Data & features**
  - Time-series split with **strict time ordering** and **leakage guards** (e.g., no future prices or news in features).
  - Feature manifests and versioned processed datasets under `data/processed/<version>/`.
- **Training & evaluation**
  - Keras model trained on engineered features, with train/val split, saved as `model.keras`.
  - Run record (`run_record.json`) captures config hash, git commit, feature columns, scaler stats, and metrics.
  - Backtest writes human-readable and JSON reports, plus optional walk-forward (fold-based) evaluation.
- **Serving & UI**
  - FastAPI app (`src/serve/app.py`) exposes `/health`, `/predict`, `/model_info` on port **8000**.
  - Streamlit frontend (`frontend/app.py`) consumes the API and `reports/latest_metrics.json` for a recruiter-friendly view.

---

## What this demonstrates for an ML engineer role

- **Production-shaped pipeline:** clear stages (ingest, features, train, backtest, serve), each with its own module and CLI entry point.
- **Time-series correctness:** explicit checks for time ordering and label leakage, enforced via unit tests.
- **Reproducibility & auditability:** every training run writes a self-describing artifact directory (config hash, git commit, metrics, schema).
- **Evaluation rigor:** baselines vs model, single-window and walk-forward backtests, plus fold stability visualizations.
- **Serving & UX:** FastAPI backend and a small, focused Streamlit UI, wired together with environment-based configuration and a `make dev` workflow.

If you’d like to see code or tests for any of these pieces during an interview, the fastest starting points are:
- `src/train/train.py` – training routine and run record.
- `src/eval/backtest.py` and `src/eval/walk_forward.py` – metrics and fold construction.
- `src/serve/app.py` – serving contract.
- `frontend/app.py` – UI that exercises the model and evaluation artifacts.

# Stock Value Forecast

**ML portfolio project** — End-to-end system for forecasting short-horizon stock trend direction from price and optional news data.

---

## Recruiter Quickstart (No API Keys)

**Demo mode is the default path.** No API keys or `.env` required. Run the full pipeline on bundled sample data in under a minute.

**1. Setup (one-time)**

```bash
git clone <repo-url>
cd stock-value-forecast
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**2. Run the demo**

```bash
make demo
```

Or directly:

```bash
python run.py demo
```

This runs **build-features → train → backtest** using `data/sample/` (config: `configs/recruiter_demo.yaml`).

**3. Expected outputs**

| What | Path |
|------|------|
| **Backtest report (human-readable)** | `reports/latest_backtest.md` |
| **Backtest metrics (JSON)** | `reports/latest_metrics.json` |
| **Model artifact** | `models/<run_id>/` (e.g. `models/demo_20240301T120000Z/`) |
| **Processed features** | `data/processed/demo/` |

Versioned copies also exist under `reports/demo/` (e.g. `reports/demo/backtest_report.md`, `reports/demo/metrics_summary.json`). Each model run directory contains `run_record.json`, `model.keras`, and `metrics_summary.json` for audit.

---

## Evaluation

After running the demo (or any backtest), open:

- **`reports/latest_backtest.md`** — Human-readable backtest summary (metrics, model vs baselines).
- **`reports/latest_metrics.json`** — Machine-readable metrics (MSE, MAE, directional accuracy, etc.).

These files are overwritten each time you run `python run.py backtest` (or `make demo`). Versioned outputs for a given dataset stay under `reports/<dataset_version>/`.

---

## API Demo

After you have a trained model (e.g. from the demo), you can start the prediction API and call it locally.

**1. Start the service**

From the repo root with your venv activated:

```bash
python run.py serve
```

Or:

```bash
make serve
```

The API listens at **http://127.0.0.1:8000**. It loads the latest model from `models/` (or use env `MODEL_RUN_ID` to pick a specific run).

**2. Example requests**

**Health check**

```bash
curl http://127.0.0.1:8000/health
```

Example response: `{"status":"ok"}`

**Model info** (version, dataset, feature schema)

```bash
curl http://127.0.0.1:8000/model_info
```

Example response: `{"model_version":"demo_20240301T120000Z","dataset_version":"demo","num_features":8,"feature_columns":[...],"training_window":{...},...}`

**Predict** (ticker + as-of date; features are looked up from processed data)

```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "as_of": "2024-01-26", "horizon": 1}'
```

Example response: `{"prediction": 0.12, "confidence": 0.8, "ticker": "AAPL", "as_of": "2024-01-26", "horizon": 1, "model_version": "demo_20240301T120000Z"}`

---

## Live APIs Mode (Optional)

To use **real market data** instead of the bundled sample, use **live mode**. This is optional; demo mode is sufficient for understanding and evaluating the pipeline.

**Required environment variables**

| Variable | Required for | How to get |
|----------|---------------|------------|
| `ALPHAVANTAGE_API_KEY` | Price ingest | [Alpha Vantage](https://www.alphavantage.co/support/#api-key) (free tier) |
| `MARKETAUX_API_KEY` | News ingest (only if `use_news: true`) | [Marketaux](https://www.marketaux.com/register) |

Create a `.env` file in the repo root (or copy `.env.example`):

```bash
ALPHAVANTAGE_API_KEY=your_alpha_vantage_key_here
# MARKETAUX_API_KEY=...   # only if use_news: true in configs/live_apis.yaml
```

**How to run ingestion**

Use the **live** config for all stages. If required keys are missing, the pipeline exits with a clear message.

```bash
# Ingest prices (and optional news)
python run.py --config configs/live_apis.yaml ingest

# Then build features, train, backtest
python run.py --config configs/live_apis.yaml build-features
python run.py --config configs/live_apis.yaml train
python run.py --config configs/live_apis.yaml backtest
```

Or run the full workflow in one go:

```bash
python run.py live
```

**Artifacts produced in live mode**

| Stage | Outputs |
|-------|---------|
| **Ingest** | `data/raw/manifests/<timestamp>.json`, `data/raw/prices/<ticker>/`, optional `data/raw/news_normalized/` |
| **Build-features** | `data/processed/<version>/features.csv`, `feature_manifest.json` |
| **Train** | `models/<run_id>/` (model.keras, run_record.json, metrics_summary.json) |
| **Backtest** | `reports/latest_backtest.md`, `reports/latest_metrics.json`, `reports/<version>/` |

---

## Problem statement and prediction task

**Primary task:** Predict **next-period trend direction** (up / down / sideways) for a given stock symbol, expressed as a continuous score in `[-1, 1]` (e.g. for use in ranking or threshold-based signals).

The problem is framed as **regression** (score) with optional conversion to a **directional label** for evaluation. The model uses engineered features from historical prices and, when enabled, from news (sentiment and article-to-stock relevancy). The goal is to demonstrate a reproducible ML pipeline (ingest → features → train → backtest → serve), not to achieve production-grade alpha.

---

## System architecture

The pipeline has five stages:

```
Ingest → Features → Train → Backtest → Serve
```

| Stage | Role |
|--------|------|
| **Ingest** | Fetch and persist raw data: historical prices (Alpha Vantage) and, optionally, news (Marketaux). Use `configs/live_apis.yaml` for live ingest; default config is `configs/recruiter_demo.yaml` (offline). |
| **Features** | Build model inputs: price-derived series, and optionally sentiment + relevancy from news. Output is a fixed-size feature vector (e.g. 8-D) per (symbol, date) with normalization stats for training and serving. |
| **Train** | Train a small neural network (e.g. 8 → 16 → dropout → 8 → 1) to predict trend score. Training is config-driven; checkpoints and artifacts go to `models/`. |
| **Backtest** | Evaluate on a held-out time period: regression metrics (e.g. MSE, MAE) and directional accuracy. Reports and plots go to `reports/`. |
| **Serve** | Load a saved model and expose a prediction API (e.g. `/predict`) for a single symbol + optional feature payload. |

End-to-end flow: **Ingest** writes to `data/`, **Features** read raw data and write feature datasets, **Train** reads features and writes to `models/`, **Backtest** reads models and feature/label data and writes to `reports/`, **Serve** loads from `models/` and serves predictions.

---

## Data sources

- **Prices (primary):** Alpha Vantage daily OHLCV (free tier only: `TIME_SERIES_DAILY`, `outputsize=compact`). Set `ALPHAVANTAGE_API_KEY` for ingest. See [docs/alpha-vantage-free-tier.md](docs/alpha-vantage-free-tier.md) for which endpoints are used and why they are free-tier compliant.
- **News (optional):** [Marketaux](https://www.marketaux.com/) financial news API. Set `use_news: true` in config and `MARKETAUX_API_KEY` in the environment. News ingest runs after price ingest; raw responses are stored under `data/raw/news/{ticker}/{ingestion_timestamp}.json`, normalized news under `data/raw/news_normalized/{version}/`, and a manifest under `data/raw/manifests/news_{version}.json`. Sentiment is aggregated by day (average sentiment, count, momentum) and merged into the price feature pipeline with a **leakage rule**: no article published after the prediction cutoff date is included in features.
- **Enrichment (optional):** Alpha Vantage SYMBOL_SEARCH, GLOBAL_QUOTE, and weekly/monthly time series. Toggle in config under `enrichment.*`; additive only, not required for training. Raw data under `data/raw/enrichment/`; manifests record what was collected. See [docs/alpha-vantage-free-tier.md](docs/alpha-vantage-free-tier.md).

Configuration is two-mode: **recruiter_demo** (default, offline, no API keys) and **live_apis** (Alpha Vantage + optional Marketaux). API keys are supplied via environment variables, not committed. With `mode: live_apis`, the pipeline fails early with a clear message if required keys are missing.

---

## Time-series split and leakage prevention

- **Split strategy:** Strict **time-based** train/validation/test. Chronological order is preserved: e.g. train on `[t0, t1)`, validate on `[t1, t2)`, test on `[t2, t3)`. No shuffling across time; no future information in training.
- **Leakage prevention:**
  - **Features:** Only use information available at or before the prediction time (e.g. past returns, past sentiment, no future prices or news).
  - **Normalization:** Fit scalers (e.g. mean/std) on **training** data only; apply the same scalers to validation and test.
  - **Labels:** Define the target (e.g. next-day return or N-day forward return) so it is known only after the feature window; no overlap between feature window and label period.

Backtest evaluation is performed only on the **test** window; validation is used for model/checkpoint selection.

---

## Baselines and evaluation methodology

- **Baselines:** Compare the neural model to at least one simple baseline, e.g.:
  - **Constant prediction:** predict 0 (no trend) for every sample.
  - **Last-return baseline:** use the most recent past return (or its sign) as the prediction.
  Additional baselines (e.g. linear model on the same features) can be added as the pipeline matures.
- **Evaluation:**
  - **Regression:** MSE, MAE (and optionally R²) on the continuous trend score on the test set.
  - **Direction:** Accuracy (and optionally precision/recall) when thresholding the score to up/down/sideways.
  - **Reporting:** Metrics and, where applicable, simple plots (e.g. predicted vs actual, time series of predictions) are written to `reports/` for reproducibility.
- **Walk-forward backtest:** When `eval.walk_forward` is set in config (e.g. `window_days: 28`, `step_days: 28`), the backtest iterates through time windows, evaluates baselines and the TensorFlow model on each window, and writes `reports/{version}/backtest_run.json` plus a human-readable `backtest_report.md`. The report can be regenerated deterministically from the stored artifact: `from src.eval.report import generate_report; generate_report("reports/<version>/backtest_run.json", "reports/<version>/backtest_report.md")`.

---

## Development

### Prerequisites

- **Python 3.9–3.12** (3.10 or 3.11 recommended for TensorFlow)
- Git

### Environment setup

From the repo root:

```bash
# Clone (if not already)
git clone https://github.com/<org>/stock-value-forecast.git
cd stock-value-forecast

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Optional: install dev tools (lint)
pip install -r requirements-dev.txt

# API keys: copy .env.example to .env in the repo root and add your keys (required for ingest)
# cp .env.example .env
# Then edit .env and set ALPHAVANTAGE_API_KEY; set MARKETAUX_API_KEY if using news (use_news: true).
# When you run pytest, .env is loaded from the repo root automatically (see tests/conftest.py).
```

From the repo root you can use `make lint` and `make test` (see Makefile).

### Lint

```bash
ruff check src tests run.py
```

Configuration is in `pyproject.toml` (`[tool.ruff]`). Fix auto-fixable issues with `ruff check --fix`.

### Tests

From the **repo root** with your venv activated:

```bash
# Run all tests (recommended before pushing)
make test
# or:
python -m pytest tests/ -v --tb=short

# Run a single test file
python -m pytest tests/test_pipeline_timeseries.py -v

# Run one test by name
python -m pytest tests/test_integration_e2e.py::test_e2e_build_features_produces_valid_artifacts_no_leakage -v

# Fast: minimal integration test only
make test-integration
```

Unit tests mock API calls, so you don’t need real API keys. Optional: add keys to `.env` if you run tests that call real APIs.

TensorFlow is optional: `tests/test_train.py` and the full e2e train/backtest tests are skipped if `tensorflow` is not installed.

### Pipeline commands

```bash
python run.py ingest      # requires ALPHAVANTAGE_API_KEY; use_news + MARKETAUX_API_KEY for news
python run.py build-features
python run.py train
python run.py backtest
python run.py serve
```

### CI and branch protection

**GitHub Actions** (`.github/workflows/ci.yml`) runs on every push and pull request to `main` / `master`:

| Job | Purpose |
|-----|--------|
| **Lint** | `ruff check` on `src`, `tests`, `run.py`. |
| **Tests** | Full `pytest` suite (Python 3.10 and 3.11). |
| **Integration** | Single minimal pipeline test: build-features on tiny data, no leakage. |

All three jobs must pass for CI to be green. To **block PRs on failing tests**: in the repo **Settings → Branches → Branch protection rules**, add a rule for `main` (or `master`) and enable **Require status checks to pass before merging**. Select the status check **CI** (or the individual jobs: **Lint**, **Tests**, **Integration**). Merges to `main` will then be blocked until CI passes.

---

## Serving API

See **API Demo** above for how to start the service and example requests. Summary:

The **Serve** stage runs a FastAPI app that loads the trained model artifact at startup (no re-training). Start it with:

```bash
make serve
# or: python run.py serve
# or: uvicorn src.serve.app:app --reload --host 127.0.0.1 --port 8000
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| **/health** | GET | Health check; returns `{"status": "ok"}`. |
| **/predict** | POST | Body: `ticker`, `as_of` (YYYY-MM-DD), `horizon` (optional, default 1). Returns `prediction` (score in [-1, 1]), `confidence` (0–1), and echoed inputs. Features are looked up from the processed dataset for the given ticker and date. |
| **/model_info** | GET | Returns `model_version` (run ID), `training_window`, `dataset_version`, and `feature_columns`. |

The service resolves the model run via `MODEL_RUN_ID` (env) or the latest run under `models/`. Optional env: `SERVE_MODELS_PATH`, `SERVE_PROCESSED_PATH` to override paths (e.g. in tests).

---

## Quickstart (pipeline stages)

Assume a Unix-like shell and Python 3.9+ with a virtual environment activated (see **Development** above).

- **Demo (default):** `python run.py demo` or `make demo` — uses `configs/recruiter_demo.yaml`, no API keys. Build-features → train → backtest on `data/sample/`.
- **Live APIs (optional):** Use `--config configs/live_apis.yaml` for every stage and set `ALPHAVANTAGE_API_KEY` (and optionally `MARKETAUX_API_KEY`) in `.env`. See **Live APIs Mode (Optional)** above.

| Stage | Demo | Live |
|--------|------|------|
| **Ingest** | *(not run in demo)* | `python run.py --config configs/live_apis.yaml ingest` |
| **Features** | (part of `make demo`) | `python run.py --config configs/live_apis.yaml build-features` |
| **Train** | (part of `make demo`) | `python run.py --config configs/live_apis.yaml train` |
| **Backtest** | (part of `make demo`) | `python run.py --config configs/live_apis.yaml backtest` |
| **Serve** | `python run.py serve` | `python run.py --config configs/live_apis.yaml serve` |

---

## Model limitations and disclaimer

- **Limitations:** The model is small and trained on a limited feature set (and possibly synthetic or short history initially). It is not designed for live trading. Performance will vary by symbol, period, and market regime; it may not generalize across time or symbols.
- **Disclaimer:** This project is for **educational and portfolio purposes only**. It is not financial advice. Stock market predictions are inherently uncertain. Do not use this system as the sole basis for investment decisions. Always do your own research and consult qualified financial advisors before making investment decisions.

---
