# Stock Value Forecast — Frontend UI

Lightweight Streamlit UI for exploring model info, predictions, and fold stability.  
**The backend API must be running first** (see main repo README).

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

With the venv **activated**, from the repo root:

```bash
streamlit run frontend/app.py
```

Or from `frontend/`:

```bash
streamlit run app.py
```

The app opens in your browser (default: http://localhost:8501).

## Backend requirement

**You must start the backend API before using live data.** From the repo root (with its own venv if you use one):

```bash
python run.py serve
```

The API runs at http://127.0.0.1:8000.
