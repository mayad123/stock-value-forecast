"""
Isolated UI layer for Stock Value Forecast.
Requires the backend API to be running (python run.py serve) for live data.
"""

import json
import math
import os
from pathlib import Path

import plotly.express as px
import requests
import streamlit as st

# Paths: repo root is parent of frontend/
_REPO_ROOT = Path(__file__).resolve().parents[1]
_LATEST_METRICS_PATH = _REPO_ROOT / "reports" / "latest_metrics.json"
# Backend base URL must come from BACKEND_URL env; no default.
_BACKEND_URL = os.environ.get("BACKEND_URL")

# Clear, consistent message when metrics file is missing (used on multiple pages)
_METRICS_FILE_MISSING_MSG = (
    "Metrics file not found. Run a backtest to generate it (e.g. `make demo` or `python run.py backtest`). "
    f"Expected path: `reports/latest_metrics.json` (relative to repo root)."
)


def _check_backend() -> bool:
    """Return True if backend is reachable (GET /health). Cached in session_state."""
    if not _BACKEND_URL:
        st.session_state["backend_reachable"] = False
        return False
    if "backend_reachable" not in st.session_state:
        try:
            r = requests.get(f"{_BACKEND_URL.rstrip('/')}/health", timeout=3)
            st.session_state["backend_reachable"] = r.ok
        except requests.RequestException:
            st.session_state["backend_reachable"] = False
    return st.session_state.get("backend_reachable", False)


st.set_page_config(
    page_title="Stock Value Forecast",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar navigation
st.sidebar.title("Stock Value Forecast")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    options=["Model Overview", "Prediction Explorer", "Fold Stability"],
    index=0,  # Default to Model Overview
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
if st.sidebar.button("Recheck backend"):
    if "backend_reachable" in st.session_state:
        del st.session_state["backend_reachable"]
    st.rerun()
st.sidebar.caption("Backend must be running: `python run.py serve`")

# BACKEND_URL must be set explicitly; if missing, show configuration error and skip all API calls.
if not _BACKEND_URL:
    st.error(
        "**Backend configuration required.** Set the `BACKEND_URL` environment variable "
        "to the running API, for example:\n\n"
        "`BACKEND_URL=http://localhost:8000`"
    )
    st.markdown(
        "The UI does not make any API calls until `BACKEND_URL` is provided. "
        "Start the backend with `python run.py serve`, then launch Streamlit with "
        "`BACKEND_URL=http://localhost:8000 streamlit run frontend/app.py`."
    )
else:
    # Backend connectivity check on startup (cached in session)
    backend_ok = _check_backend()

    # Warning banner if backend unreachable
    if not backend_ok:
        st.warning(
            "**Backend is unreachable.** Model Overview and Prediction Explorer need the API. "
            f"Start it with: `python run.py serve` (expected: BACKEND_URL={_BACKEND_URL})"
        )


    # Route to pages (wrapped so no unhandled exceptions during navigation)
    try:
        if page == "Model Overview":
        st.header("Model Overview")
        st.markdown(
            "Shows the loaded model’s version, dataset, feature schema, and aggregate backtest metrics, with a baseline comparison. "
            "This supports **reproducibility**: you can see exactly which artifact and data version produced the results, and **evaluation rigor**: the model is compared to simple baselines on the same test set."
        )
        st.divider()

        # Load metadata from backend (with loading indicator)
        model_info = None
        model_info_error = None
        with st.spinner("Loading model metadata…"):
            try:
                r = requests.get(f"{_BACKEND_URL.rstrip('/')}/model_info", timeout=5)
                if r.ok:
                    model_info = r.json()
                else:
                    model_info_error = f"Backend returned {r.status_code}: {r.text[:200] if r.text else 'No body'}"
            except requests.RequestException as e:
                st.session_state["backend_reachable"] = False
                model_info_error = f"Could not reach backend at {_BACKEND_URL}: {e}"

        # Load aggregate metrics from file
        metrics_data = None
        metrics_error = None
        if _LATEST_METRICS_PATH.exists():
            try:
                with open(_LATEST_METRICS_PATH) as f:
                    metrics_data = json.load(f)
                if not isinstance(metrics_data.get("models"), dict):
                    metrics_error = "reports/latest_metrics.json has no valid 'models' object."
                    metrics_data = None
            except (json.JSONDecodeError, OSError) as e:
                metrics_error = f"Could not read reports/latest_metrics.json: {e}"
        else:
            metrics_error = _METRICS_FILE_MISSING_MSG

        # Error panel if either source failed
        if model_info_error or metrics_error:
            st.error("**Model Overview is missing one or more data sources.**")
            if model_info_error:
                st.markdown(f"- **Backend (/model_info):** {model_info_error}")
            if metrics_error:
                st.markdown(f"- **Metrics file:** {metrics_error}")
            st.markdown("Ensure the backend is running (`python run.py serve`) and a backtest has been run so that `reports/latest_metrics.json` exists.")
        else:
            # Metadata section
            st.subheader("Metadata")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Model version", model_info.get("model_version", "—"))
            with c2:
                st.metric("Dataset version", model_info.get("dataset_version", "—"))
            with c3:
                st.metric("Number of features", model_info.get("num_features", "—"))
            with c4:
                st.metric("Schema fingerprint", (model_info.get("feature_schema_fingerprint") or "—")[:16] + "…" if (model_info.get("feature_schema_fingerprint") and len(model_info.get("feature_schema_fingerprint", "")) > 16) else (model_info.get("feature_schema_fingerprint") or "—"))

            if model_info.get("training_window"):
                with st.expander("Training window"):
                    st.json(model_info["training_window"])
            if model_info.get("feature_columns"):
                with st.expander("Feature columns"):
                    st.write(", ".join(model_info["feature_columns"]))

            # Aggregate evaluation metrics
            st.subheader("Aggregate evaluation metrics")
            models = metrics_data.get("models") or {}
            if not models:
                st.info("No model metrics in latest_metrics.json (empty backtest?).")
            else:
                # Table: rows = models, cols = metric names
                metric_keys = ["mse", "rmse", "mae", "r2", "directional_accuracy", "n_samples"]
                rows = []
                for name, m in models.items():
                    row = {"Model": name}
                    for k in metric_keys:
                        v = m.get(k)
                        if v is None or (isinstance(v, float) and math.isnan(v)):
                            row[k] = "N/A"
                        else:
                            row[k] = round(v, 6) if isinstance(v, float) else v
                    rows.append(row)
                st.dataframe(rows, use_container_width=True, hide_index=True)

                # Baseline vs model comparison chart (bar chart per metric)
                st.subheader("Baseline vs model comparison")
                chart_metrics = ["mse", "mae", "directional_accuracy"]
                chart_data = []
                for model_name, m in models.items():
                    for mk in chart_metrics:
                        v = m.get(mk)
                        if v is not None and not (isinstance(v, float) and math.isnan(v)):
                            chart_data.append({"Model": model_name, "Metric": mk, "Value": float(v)})
                if chart_data:
                    fig = px.bar(
                        chart_data,
                        x="Model",
                        y="Value",
                        color="Model",
                        facet_row="Metric",
                        barmode="group",
                        title="Metrics by model (MSE, MAE, directional accuracy)",
                    )
                    fig.update_layout(showlegend=False)
                    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No plottable metrics (all NaN or missing).")

    elif page == "Prediction Explorer":
        st.header("Prediction Explorer")
        st.markdown(
            "Run a single prediction for a ticker and as-of date; the backend looks up features from processed data and returns a trend score. "
            "This demonstrates **serving** the trained model with the same schema used in training, and keeps **reproducibility** explicit (model version and inputs are shown in the response)."
        )
        st.divider()

        with st.form("predict_form"):
            ticker = st.text_input("Ticker", value="AAPL", max_chars=10, help="Stock symbol (e.g. AAPL, MSFT)")
            as_of = st.text_input("Date", value="2024-01-26", help="As-of date for features (YYYY-MM-DD)")
            horizon = st.number_input("Horizon (days)", min_value=1, max_value=30, value=1)
            submitted = st.form_submit_button("Get prediction")

        if submitted:
            ticker = (ticker or "").strip().upper()
            as_of = (as_of or "").strip()
            if not ticker or not as_of:
                st.error("Please provide both Ticker and Date.")
            else:
                try:
                    with st.spinner("Calling prediction API…"):
                        r = requests.post(
                            f"{_BACKEND_URL.rstrip('/')}/predict",
                            json={"ticker": ticker, "as_of": as_of, "horizon": horizon},
                            timeout=10,
                        )
                    if r.ok:
                        data = r.json()
                        st.success("Prediction returned successfully.")
                        st.metric("Predicted value (trend score)", data.get("prediction", "—"))
                        c1, c2 = st.columns(2)
                        with c1:
                            st.metric("Confidence", data.get("confidence", "—"))
                            st.caption("Model version: " + (data.get("model_version") or "—"))
                        with c2:
                            st.caption(f"Ticker: {data.get('ticker', '—')}")
                            st.caption(f"As-of date: {data.get('as_of', '—')}")
                            st.caption(f"Horizon: {data.get('horizon', '—')} day(s)")
                        with st.expander("Full response"):
                            st.json(data)
                    else:
                        st.error("**Backend returned an error.**")
                        st.markdown(f"- **Status:** {r.status_code}")
                        try:
                            err_body = r.json()
                            st.markdown("- **Response:**")
                            st.json(err_body)
                        except Exception:
                            if r.text:
                                st.code(r.text[:500], language="text")
                        st.caption("Check that ticker and date exist in processed data (e.g. run demo and use a date within the sample range).")
                except requests.RequestException as e:
                    st.session_state["backend_reachable"] = False
                    st.error(f"**Could not reach backend:** {e}")
                    st.caption(f"Ensure the API is running at {_BACKEND_URL} (e.g. `python run.py serve`).")

    elif page == "Fold Stability":
        st.header("Fold Stability")
        st.markdown(
            "Shows per-fold train/test date ranges, metrics per model per fold, and aggregate mean ± std across folds, with a chart of metric variability. "
            "This supports **evaluation rigor**: stability across time windows indicates the setup is not overfitting to a single split."
        )
        st.divider()

        # Load from same file as Model Overview
        if not _LATEST_METRICS_PATH.exists():
            st.error("**Metrics file not found.**")
            st.markdown(_METRICS_FILE_MISSING_MSG)
            st.markdown("For fold data, use a config with walk-forward enabled (`eval.fold_size_days`, `eval.step_size_days`).")
        else:
            try:
                with open(_LATEST_METRICS_PATH) as f:
                    fold_data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                st.error(f"**Could not read metrics file:** {e}")
                st.caption(_METRICS_FILE_MISSING_MSG)
            else:
                folds = fold_data.get("folds") or []
                aggregate = fold_data.get("aggregate") or {}

                if len(folds) < 2:
                    st.warning(
                        "**Walk-forward requires multiple folds.** This page shows fold-level stability. "
                        "Run a backtest with walk-forward config (e.g. `eval.fold_size_days`, `eval.step_size_days`) to get at least 2 folds."
                    )
                    if folds:
                        st.markdown("Current file has 1 fold; at least 2 are needed for variability analysis.")
                else:
                    # Table of folds: Fold ID, Train date range, Test date range, n_samples
                    st.subheader("Folds")
                    fold_rows = []
                    for idx, f in enumerate(folds):
                        fold_rows.append({
                            "Fold ID": f.get("fold_id", idx),
                            "Train start": f.get("train_start", "—"),
                            "Train end": f.get("train_end", "—"),
                            "Test start": f.get("test_start", "—"),
                            "Test end": f.get("test_end", "—"),
                            "n_samples": f.get("n_samples", "—"),
                        })
                    st.dataframe(fold_rows, use_container_width=True, hide_index=True)

                    # Metrics per model per fold (nested table or expandable)
                    st.subheader("Metrics per fold (by model)")
                    metric_keys = ["mse", "mae", "directional_accuracy"]
                    # Build long-format rows: fold_id, model, mse, mae, directional_accuracy
                    per_fold_rows = []
                    for idx, f in enumerate(folds):
                        fid = f.get("fold_id", idx)
                        for model_name, m in (f.get("metrics") or {}).items():
                            row = {"Fold ID": fid, "Model": model_name}
                            for k in metric_keys:
                                v = m.get(k)
                                if v is not None and not (isinstance(v, float) and math.isnan(v)):
                                    row[k] = round(v, 6) if isinstance(v, float) else v
                                else:
                                    row[k] = "N/A"
                            per_fold_rows.append(row)
                    if per_fold_rows:
                        st.dataframe(per_fold_rows, use_container_width=True, hide_index=True)
                    else:
                        st.info("No per-fold metrics in file.")

                    # Aggregate: mean and std per model per metric
                    st.subheader("Aggregate (mean ± std across folds)")
                    if aggregate:
                        agg_rows = []
                        for model_name, metrics in aggregate.items():
                            for metric_key, stats in (metrics or {}).items():
                                if isinstance(stats, dict) and "mean" in stats and "std" in stats:
                                    mean_v = stats["mean"]
                                    std_v = stats["std"]
                                    if not (isinstance(mean_v, float) and math.isnan(mean_v)):
                                        agg_rows.append({
                                            "Model": model_name,
                                            "Metric": metric_key,
                                            "Mean": round(mean_v, 6),
                                            "Std": round(std_v, 6),
                                        })
                        if agg_rows:
                            st.dataframe(agg_rows, use_container_width=True, hide_index=True)
                        else:
                            st.info("No aggregate mean/std in file.")
                    else:
                        st.info("No aggregate block in file.")

                    # Visual: fold metric variability across folds
                    st.subheader("Fold metric variability")
                    chart_metrics = ["mse", "mae", "directional_accuracy"]
                    chart_data = []
                    for idx, f in enumerate(folds):
                        fid = f.get("fold_id", idx)
                        for model_name, m in (f.get("metrics") or {}).items():
                            for mk in chart_metrics:
                                v = m.get(mk)
                                if v is not None and not (isinstance(v, float) and math.isnan(v)):
                                    chart_data.append({
                                        "Fold ID": fid,
                                        "Model": model_name,
                                        "Metric": mk,
                                        "Value": float(v),
                                    })
                    if chart_data:
                        fig = px.line(
                            chart_data,
                            x="Fold ID",
                            y="Value",
                            color="Model",
                            facet_row="Metric",
                            markers=True,
                            title="Metric value by fold (variability across folds)",
                        )
                        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No plottable per-fold metrics.")

except Exception as e:
    st.error("**Something went wrong on this page.**")
    st.code(str(e), language="text")
    st.caption("If this persists, check the browser console or restart the app.")
