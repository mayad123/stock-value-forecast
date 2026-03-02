# Stock Value Forecast

**ML portfolio project** — End-to-end system for forecasting short-horizon stock trend direction from price and optional news data.

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
| **Ingest** | Fetch and persist raw data: historical prices (Alpha Vantage) and, optionally, news (Marketaux). Company symbols and config are loaded from `configs/default.yaml`. |
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

All ingest is configuration-driven (`configs/default.yaml`); API keys are supplied via environment variables, not committed.

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

## Quick start (run with APIs)

End-to-end run with real API keys: ingest data → build features → train → (optional) backtest → serve.

**1. One-time setup**

```bash
cd stock-value-forecast
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

**2. Add your API keys**

- Get a free key: [Alpha Vantage](https://www.alphavantage.co/support/#api-key) (prices). Optional: [Marketaux](https://www.marketaux.com/register) (news).
- In the repo root, create `.env` (or copy from `.env.example`) and set:

```bash
# .env (in repo root)
ALPHAVANTAGE_API_KEY=your_alpha_vantage_key_here
MARKETAUX_API_KEY=your_marketaux_key_here
```

(Leave `MARKETAUX_API_KEY` empty if you’re not using news; keep `use_news: false` in `configs/default.yaml`.)

**3. Run the pipeline**

From the repo root with venv activated:

```bash
# Ingest prices (and news if use_news: true and MARKETAUX_API_KEY set)
python run.py ingest

# Build features from ingested data
python run.py build-features

# Train model (writes to models/)
python run.py train

# Optional: run backtest
python run.py backtest

# Start the prediction API (loads latest model)
python run.py serve
```

The API will be at **http://127.0.0.1:8000**. Try `GET /health`, `GET /model_info`, and `POST /predict` with a JSON body like `{"ticker": "AAPL", "as_of": "2024-01-15", "horizon": 1}`.

**Using Make:** `make ingest`, `make build-features`, `make train`, `make backtest`, `make serve`.

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

Assume a Unix-like shell and Python 3.9+ with a virtual environment activated (see **Development** above). Config and env (e.g. `DATA_DIR`, `MODEL_DIR`) can be set in `configs/default.yaml` or environment variables.

| Stage | Command (placeholder) | Purpose |
|--------|------------------------|--------|
| **Ingest** | `python -m src.ingest.run --config configs/default.yaml` | Fetch and save raw price (and optional news) data. |
| **Features** | `python -m src.features.run --config configs/default.yaml` | Build feature vectors and normalization stats from raw data. |
| **Train** | `python -m src.train.train --config configs/default.yaml` | Train model; save checkpoints and final artifact to `models/`. |
| **Backtest** | `python -m src.eval.run --config configs/default.yaml` | Run evaluation and write metrics/plots to `reports/`. |
| **Serve** | `uvicorn src.serve.app:app --reload` | Start the prediction API (loads model from `models/`). |

Exact entry points (e.g. `src.ingest.run`) may be added or renamed as the codebase is implemented; the table above defines the intended usage per stage.

---

## Model limitations and disclaimer

- **Limitations:** The model is small and trained on a limited feature set (and possibly synthetic or short history initially). It is not designed for live trading. Performance will vary by symbol, period, and market regime; it may not generalize across time or symbols.
- **Disclaimer:** This project is for **educational and portfolio purposes only**. It is not financial advice. Stock market predictions are inherently uncertain. Do not use this system as the sole basis for investment decisions. Always do your own research and consult qualified financial advisors before making investment decisions.

---
