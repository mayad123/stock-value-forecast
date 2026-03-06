# Stock Value Forecast — Frontend UI

Lightweight Streamlit UI for exploring model info, predictions, and fold stability.  
**The backend API must be running first** (see main repo README).

## Structure

- **`app.py`** — Streamlit entry point: page config, sidebar, routing, and page renderers. Stays thin by delegating to the modules below.
- **`api_client.py`** — All HTTP calls to the backend (health, metrics, predictions, model_info, predict, prices, feature_importance). Returns data or error strings; no Streamlit.
- **`data_access.py`** — Local file access (e.g. `reports/latest_metrics.json` for Model Overview / Fold Stability). API-first pages use `api_client` instead.
- **`format.py`** — Formatting and table/chart data helpers (metric display, metrics tables, fold rows, chart data for Plotly). Pure functions, no Streamlit.

## Setup (venv)

Create and activate a virtual environment, then install dependencies.

**From the repo root:**

```bash
cd stock-value-forecast
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r frontend/requirements.txt
```

**Or from the `frontend/` directory** (venv lives inside frontend):

```bash
cd frontend
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run the UI

Set `BACKEND_URL` to the running API (no default). With the venv **activated**, from the repo root:

```bash
BACKEND_URL=http://localhost:8000 streamlit run frontend/app.py
```

Or from `frontend/`:

```bash
BACKEND_URL=http://localhost:8000 streamlit run app.py
```

The app opens in your browser (default: http://localhost:8501).

## Backend requirement

**Start the backend API first.** From the repo root (with its own venv if you use one):

```bash
python run.py serve
```

The API runs at http://127.0.0.1:8000. The UI requires `BACKEND_URL`; if it is unset, the app shows a configuration error and does not call the API.
