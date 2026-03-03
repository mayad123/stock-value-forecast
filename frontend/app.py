"""
Isolated UI layer for Stock Value Forecast.
Requires the backend API to be running (python run.py serve). Evaluation page uses GET /metrics and GET /predictions only (no file access).
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
_BACKEND_URL = (os.environ.get("BACKEND_URL") or "").strip() or None
_BACKEND_TIMEOUT = int(os.environ.get("BACKEND_TIMEOUT", "60"))

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
            r = requests.get(f"{_BACKEND_URL.rstrip('/')}/health", timeout=_BACKEND_TIMEOUT)
            st.session_state["backend_reachable"] = r.ok
        except requests.RequestException:
            st.session_state["backend_reachable"] = False
    return st.session_state.get("backend_reachable", False)


st.set_page_config(
    page_title="Stock Value Forecast — Evaluation",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Sidebar navigation — Evaluation is default (index 0)
st.sidebar.title("Stock Value Forecast")
st.sidebar.caption("ML evaluation & serving")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    options=[
        "Evaluation",
        "Model Overview",
        "Prediction Explorer",
        "Fold Stability",
        "Price + Backtest Overlay",
    ],
    index=0,
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
if st.sidebar.button("Recheck backend"):
    if "backend_reachable" in st.session_state:
        del st.session_state["backend_reachable"]
    st.rerun()
st.sidebar.caption("Backend: `python run.py serve`")

# Try It — single prediction (one click = one POST /predict)
if _BACKEND_URL:
    with st.sidebar.expander("Try It — single prediction"):
        tryit_ticker = st.text_input("Ticker", value="AAPL", max_chars=10, key="tryit_ticker")
        tryit_date = st.text_input("Date (YYYY-MM-DD)", value="2024-01-26", key="tryit_date")
        tryit_clicked = st.button("Get prediction", key="tryit_btn")
        if tryit_clicked:
            t = (tryit_ticker or "").strip().upper()
            d = (tryit_date or "").strip()
            if not t or not d:
                st.error("Ticker and date are required.")
            else:
                try:
                    # One on-demand /predict call per click
                    base = _BACKEND_URL.rstrip("/")
                    r = requests.post(
                        f"{base}/predict",
                        json={"ticker": t, "as_of": d, "horizon": 1},
                        timeout=_BACKEND_TIMEOUT,
                    )
                    if r.ok:
                        data = r.json()
                        pred_val = data.get("prediction", None)
                        model_version = data.get("model_version") or "—"

                        # Best-effort fetch of current price (most recent <= as_of) via /prices
                        price_current = None
                        try:
                            r_price = requests.get(
                                f"{base}/prices",
                                params={"ticker": t, "end_date": d},
                                timeout=_BACKEND_TIMEOUT,
                            )
                            if r_price.ok:
                                prices = r_price.json() if isinstance(r_price.json(), list) else []
                                if prices:
                                    # Take the last row (latest date <= as_of)
                                    last = prices[-1]
                                    if "adjusted_close" in last:
                                        price_current = float(last["adjusted_close"])
                                    elif "close" in last:
                                        price_current = float(last["close"])
                        except requests.RequestException:
                            price_current = None

                        # Best-effort fetch of dataset version via /model_info
                        dataset_version = "—"
                        try:
                            r_info = requests.get(f"{base}/model_info", timeout=_BACKEND_TIMEOUT)
                            if r_info.ok:
                                info = r_info.json()
                                dataset_version = info.get("dataset_version", "—")
                        except requests.RequestException:
                            dataset_version = "—"

                        st.success("Prediction received.")

                        # Compute implied next-day price if we have both prediction and current price
                        price_next = None
                        if isinstance(pred_val, (int, float)) and price_current is not None:
                            try:
                                price_next = price_current * (1.0 + float(pred_val))
                            except Exception:
                                price_next = None

                        # Display: current price, predicted return (as %), implied next-day price
                        c1, c2 = st.columns(2)
                        with c1:
                            if price_current is not None:
                                st.metric("Current price", f"{price_current:,.2f}")
                            else:
                                st.metric("Current price", "N/A")
                            if isinstance(pred_val, (int, float)):
                                st.metric(
                                    "Predicted 1-day simple return",
                                    f"{float(pred_val) * 100:.2f}%",
                                )
                            else:
                                st.metric("Predicted 1-day simple return", "N/A")
                        with c2:
                            if price_next is not None:
                                st.metric("Implied next-day price", f"{price_next:,.2f}")
                            else:
                                st.metric("Implied next-day price", "N/A")
                            st.caption(f"Model version: {model_version}")
                            st.caption(f"Dataset version: {dataset_version}")
                    else:
                        try:
                            err = r.json()
                            detail = err.get("detail", r.text)
                        except Exception:
                            detail = r.text or f"Status {r.status_code}"
                        st.error("Error: " + (detail[:300] if isinstance(detail, str) else str(detail)[:300]))
                except requests.RequestException as e:
                    st.error("Request failed: " + str(e))

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
            "**Backend is unreachable.** Evaluation and other pages need the API. "
            f"Start it with: `python run.py serve` (expected: BACKEND_URL={_BACKEND_URL})"
        )


    # Route to pages (wrapped so no unhandled exceptions during navigation)
    try:
        if page == "Evaluation":
            # Evaluation-centric default page: backend only (GET /metrics, GET /predictions), no file access
            st.header("Evaluation")
            st.markdown(
                "Aggregate backtest metrics, baseline vs model comparison, and walk-forward fold stability. "
                "All data is loaded from the backend API."
            )
            st.divider()

            metrics_data = None
            predictions_data = []
            metrics_error = None
            predictions_error = None
            base = f"{_BACKEND_URL.rstrip('/')}"
            with st.spinner("Loading evaluation data…"):
                try:
                    r = requests.get(f"{base}/metrics", timeout=_BACKEND_TIMEOUT)
                    if r.ok:
                        metrics_data = r.json()
                    else:
                        metrics_error = f"/metrics returned {r.status_code}"
                except requests.RequestException as e:
                    metrics_error = str(e)
                    st.session_state["backend_reachable"] = False
                try:
                    r = requests.get(f"{base}/predictions", timeout=_BACKEND_TIMEOUT)
                    if r.ok:
                        predictions_data = r.json() if isinstance(r.json(), list) else []
                    else:
                        predictions_error = f"/predictions returned {r.status_code}"
                except requests.RequestException as e:
                    predictions_error = str(e)

            if metrics_error:
                st.error("**Could not load metrics.** " + metrics_error)
                st.caption("Ensure the backend is running and a backtest has been run (e.g. `make demo`).")
            elif metrics_data is None:
                st.warning("No metrics data available.")
            else:
                models = metrics_data.get("models") or {}
                folds = metrics_data.get("folds") or []
                aggregate = metrics_data.get("aggregate") or {}

                # Filters (ticker, model_name, fold_id) — options from data
                tickers = sorted(set(p.get("ticker") for p in predictions_data if p.get("ticker")))
                model_names = sorted(models.keys()) if models else sorted(set(p.get("model_name") for p in predictions_data if p.get("model_name")))
                fold_ids = sorted(set(p.get("fold_id") for p in predictions_data if p.get("fold_id") is not None))

                st.sidebar.markdown("**Filters**")
                filter_ticker = st.sidebar.multiselect("Ticker", options=["All"] + tickers, default=["All"], key="eval_ticker")
                filter_model = st.sidebar.multiselect("Model", options=["All"] + model_names, default=["All"], key="eval_model")
                filter_fold = st.sidebar.multiselect("Fold ID", options=["All"] + [str(i) for i in fold_ids], default=["All"], key="eval_fold")

                use_all_tickers = "All" in filter_ticker or not filter_ticker
                use_all_models = "All" in filter_model or not filter_model
                use_all_folds = "All" in filter_fold or not filter_fold
                selected_fold_ids = None if use_all_folds else [int(x) for x in filter_fold if x != "All" and x.isdigit()]

                # 1) Aggregate metrics table
                st.subheader("Aggregate metrics")
                if not models:
                    st.info("No model metrics (run a backtest).")
                else:
                    metric_keys = ["mse", "rmse", "mae", "r2", "directional_accuracy", "n_samples"]
                    rows = []
                    for name, m in models.items():
                        if not use_all_models and name not in filter_model:
                            continue
                        row = {"Model": name}
                        for k in metric_keys:
                            v = m.get(k)
                            if v is None or (isinstance(v, float) and math.isnan(v)):
                                row[k] = "N/A"
                            else:
                                row[k] = round(v, 6) if isinstance(v, float) else v
                        rows.append(row)
                    if rows:
                        st.dataframe(rows, use_container_width=True, hide_index=True)
                    else:
                        st.caption("No models match the selected filter.")

                # 2) Baseline vs model comparison
                st.subheader("Baseline vs model comparison")
                if models:
                    chart_metrics = ["mse", "mae", "directional_accuracy"]
                    chart_data = []
                    for model_name, m in models.items():
                        if not use_all_models and model_name not in filter_model:
                            continue
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
                            title="Metrics by model",
                        )
                        fig.update_layout(showlegend=False)
                        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No plottable metrics.")

                # 3) Fold stability
                st.subheader("Fold stability")
                folds_filtered = [f for f in folds if use_all_folds or f.get("fold_id") in (selected_fold_ids or [])]
                if len(folds) < 2:
                    st.warning(
                        "Walk-forward needs at least 2 folds. Run a backtest with `eval.fold_size_days` and `eval.step_size_days`."
                    )
                    if folds:
                        fold_rows = [{"Fold ID": f.get("fold_id"), "Train start": f.get("train_start"), "Train end": f.get("train_end"), "Test start": f.get("test_start"), "Test end": f.get("test_end"), "n_samples": f.get("n_samples")} for f in folds]
                        st.dataframe(fold_rows, use_container_width=True, hide_index=True)
                else:
                    fold_rows = []
                    for f in folds_filtered:
                        fold_rows.append({
                            "Fold ID": f.get("fold_id", "—"),
                            "Train start": f.get("train_start", "—"),
                            "Train end": f.get("train_end", "—"),
                            "Test start": f.get("test_start", "—"),
                            "Test end": f.get("test_end", "—"),
                            "n_samples": f.get("n_samples", "—"),
                        })
                    if fold_rows:
                        st.dataframe(fold_rows, use_container_width=True, hide_index=True)

                    # Per-fold metrics (by model)
                    st.caption("Metrics per fold (by model)")
                    per_fold_rows = []
                    for f in folds_filtered:
                        fid = f.get("fold_id", "—")
                        for model_name, m in (f.get("metrics") or {}).items():
                            if not use_all_models and model_name not in filter_model:
                                continue
                            row = {"Fold ID": fid, "Model": model_name}
                            for k in ["mse", "mae", "directional_accuracy"]:
                                v = m.get(k)
                                row[k] = round(v, 6) if v is not None and not (isinstance(v, float) and math.isnan(v)) else "N/A"
                            per_fold_rows.append(row)
                    if per_fold_rows:
                        st.dataframe(per_fold_rows, use_container_width=True, hide_index=True)

                    # Aggregate mean ± std across folds
                    if aggregate:
                        st.caption("Aggregate (mean ± std across folds)")
                        agg_rows = []
                        for model_name, metrics in aggregate.items():
                            if not use_all_models and model_name not in filter_model:
                                continue
                            for metric_key, stats in (metrics or {}).items():
                                if isinstance(stats, dict) and "mean" in stats and "std" in stats:
                                    mean_v, std_v = stats["mean"], stats["std"]
                                    if not (isinstance(mean_v, float) and math.isnan(mean_v)):
                                        agg_rows.append({"Model": model_name, "Metric": metric_key, "Mean": round(mean_v, 6), "Std": round(std_v, 6)})
                        if agg_rows:
                            st.dataframe(agg_rows, use_container_width=True, hide_index=True)

                    # Fold metric variability chart
                    st.caption("Metric value by fold")
                    chart_data = []
                    for f in folds_filtered:
                        fid = f.get("fold_id")
                        for model_name, m in (f.get("metrics") or {}).items():
                            if not use_all_models and model_name not in filter_model:
                                continue
                            for mk in ["mse", "mae", "directional_accuracy"]:
                                v = m.get(mk)
                                if v is not None and not (isinstance(v, float) and math.isnan(v)):
                                    chart_data.append({"Fold ID": fid, "Model": model_name, "Metric": mk, "Value": float(v)})
                    if chart_data:
                        fig = px.line(
                            chart_data,
                            x="Fold ID",
                            y="Value",
                            color="Model",
                            facet_row="Metric",
                            markers=True,
                        )
                        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
                        st.plotly_chart(fig, use_container_width=True)

                # Filtered predictions table (from GET /predictions)
                pred_filtered = list(predictions_data)
                if not use_all_tickers and tickers:
                    pred_filtered = [p for p in pred_filtered if p.get("ticker") in filter_ticker]
                if not use_all_models and model_names:
                    pred_filtered = [p for p in pred_filtered if p.get("model_name") in filter_model]
                if not use_all_folds and selected_fold_ids is not None:
                    pred_filtered = [p for p in pred_filtered if p.get("fold_id") in selected_fold_ids]
                if predictions_data is not None:
                    st.subheader("Predictions")
                    if predictions_error and not predictions_data:
                        st.caption("Predictions could not be loaded: " + predictions_error)
                    elif pred_filtered:
                        st.dataframe(pred_filtered[:500], use_container_width=True, hide_index=True)
                        if len(pred_filtered) > 500:
                            st.caption(f"Showing first 500 of {len(pred_filtered)} rows.")
                    else:
                        st.caption("No prediction rows, or none match the current filters.")

        elif page == "Model Overview":
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
                    r = requests.get(f"{_BACKEND_URL.rstrip('/')}/model_info", timeout=_BACKEND_TIMEOUT)
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
                    # Defensive: file must be a dict with a 'models' object
                    if not isinstance(metrics_data, dict) or not isinstance(metrics_data.get("models"), dict):
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
                                timeout=_BACKEND_TIMEOUT,
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
                    if not isinstance(fold_data, dict):
                        st.error("**Metrics file has invalid format (expected JSON object).**")
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

        elif page == "Price + Backtest Overlay":
            st.header("Price + Backtest Overlay")
            st.markdown(
                "Visualize **backtest-window predictions** against historical prices for a selected ticker. "
                "This page is for recruiter-friendly intuition, not live trading."
            )
            st.divider()

            base = f"{_BACKEND_URL.rstrip('/')}"
            predictions_data = []
            predictions_error = None
            with st.spinner("Loading predictions…"):
                try:
                    r = requests.get(f"{base}/predictions", timeout=_BACKEND_TIMEOUT)
                    if r.ok:
                        predictions_data = r.json() if isinstance(r.json(), list) else []
                    else:
                        predictions_error = f"/predictions returned {r.status_code}"
                except requests.RequestException as e:
                    predictions_error = str(e)

            if predictions_error:
                st.error("**Could not load predictions.** " + predictions_error)
                st.caption(
                    "Ensure the backend is running and a backtest has been run "
                    "(e.g. `make demo` or `python run.py demo-real`)."
                )
            elif not predictions_data:
                st.info("No predictions available. Run a backtest first.")
            else:
                import pandas as pd

                pred_df = pd.DataFrame(predictions_data)
                if "ticker" not in pred_df.columns or "target_date" not in pred_df.columns:
                    st.error("Predictions payload missing required columns.")
                else:
                    pred_df["ticker"] = pred_df["ticker"].astype(str)
                    pred_df["target_date"] = pd.to_datetime(pred_df["target_date"])

                    tickers = sorted(pred_df["ticker"].unique())
                    model_names = sorted(pred_df["model_name"].unique()) if "model_name" in pred_df.columns else []

                    c1, c2 = st.columns([1, 1])
                    with c1:
                        sel_ticker = st.selectbox("Ticker", options=tickers, index=0)
                    with c2:
                        # Default to all models; user can narrow down to a specific one
                        default_models = model_names
                        sel_models = st.multiselect(
                            "Models (backtest)",
                            options=model_names,
                            default=default_models,
                        )

                    pred_t = pred_df[pred_df["ticker"] == sel_ticker]
                    if sel_models:
                        pred_t = pred_t[pred_t["model_name"].isin(sel_models)]

                    if pred_t.empty:
                        st.info("No prediction rows for this ticker / model selection.")
                    else:
                        # Date range from target_date
                        min_date = pred_t["target_date"].min().strftime("%Y-%m-%d")
                        max_date = pred_t["target_date"].max().strftime("%Y-%m-%d")

                        # Fetch prices for the same window
                        prices_error = None
                        prices_data = []
                        with st.spinner(f"Loading prices for {sel_ticker}…"):
                            try:
                                r = requests.get(
                                    f"{base}/prices",
                                    params={"ticker": sel_ticker, "start_date": min_date, "end_date": max_date},
                                    timeout=_BACKEND_TIMEOUT,
                                )
                                if r.ok:
                                    prices_data = r.json() if isinstance(r.json(), list) else []
                                else:
                                    prices_error = f"/prices returned {r.status_code}"
                            except requests.RequestException as e:
                                prices_error = str(e)

                        if prices_error:
                            st.error("**Could not load prices.** " + prices_error)
                        elif not prices_data:
                            st.info("No price data available for this ticker and date range.")
                        else:
                            prices_df = pd.DataFrame(prices_data)
                            if "date" not in prices_df.columns:
                                st.error("Price payload missing 'date' column.")
                            else:
                                prices_df["date"] = pd.to_datetime(prices_df["date"])
                                # Prefer adjusted_close, fall back to close
                                price_col = None
                                for c in ["adjusted_close", "close"]:
                                    if c in prices_df.columns:
                                        price_col = c
                                        break
                                if price_col is None:
                                    st.error("Price payload missing adjusted_close/close columns.")
                                else:
                                    prices_df = prices_df.sort_values("date")

                                    # Plot 1: price line
                                    st.subheader(f"Price for {sel_ticker}")
                                    fig_price = px.line(
                                        prices_df,
                                        x="date",
                                        y=price_col,
                                        title=f"{sel_ticker} price (demo dataset)",
                                    )
                                    fig_price.update_layout(xaxis_title="Date", yaxis_title=price_col)
                                    st.plotly_chart(fig_price, use_container_width=True)

                                    # Prepare prediction series aligned by target_date
                                    st.subheader("Backtest predictions vs actual target")
                                    pred_plot = pred_t.copy()
                                    pred_plot["target_date"] = pred_plot["target_date"].dt.strftime("%Y-%m-%d")

                                    # Melt into long format: y_true vs y_pred per model
                                    series_rows = []
                                    for _, row in pred_plot.iterrows():
                                        td = row["target_date"]
                                        if "y_true" in row and not pd.isna(row["y_true"]):
                                            series_rows.append(
                                                {
                                                    "target_date": td,
                                                    "value": float(row["y_true"]),
                                                    "Series": "Actual (y_true)",
                                                }
                                            )
                                        if "y_pred" in row and not pd.isna(row["y_pred"]):
                                            label = f"Pred ({row['model_name']})"
                                            series_rows.append(
                                                {
                                                    "target_date": td,
                                                    "value": float(row["y_pred"]),
                                                    "Series": label,
                                                }
                                            )
                                    if series_rows:
                                        series_df = pd.DataFrame(series_rows)
                                        fig_pred = px.line(
                                            series_df,
                                            x="target_date",
                                            y="value",
                                            color="Series",
                                            markers=True,
                                            title="Predicted vs actual forward return (backtest windows)",
                                        )
                                        fig_pred.update_layout(
                                            xaxis_title="Target date",
                                            yaxis_title="Forward return",
                                        )
                                        st.plotly_chart(fig_pred, use_container_width=True)
                                    else:
                                        st.caption("No plottable prediction series.")

                                    # Optional error plot: y_pred - y_true
                                    if "y_true" in pred_t.columns and "y_pred" in pred_t.columns:
                                        st.subheader("Prediction error (y_pred - y_true)")
                                        err_rows = []
                                        for _, row in pred_t.iterrows():
                                            if pd.isna(row.get("y_true")) or pd.isna(row.get("y_pred")):
                                                continue
                                            err_rows.append(
                                                {
                                                    "target_date": row["target_date"],
                                                    "Error": float(row["y_pred"] - row["y_true"]),
                                                    "Model": row.get("model_name"),
                                                }
                                            )
                                        if err_rows:
                                            err_df = pd.DataFrame(err_rows)
                                            err_df["target_date"] = err_df["target_date"].dt.strftime("%Y-%m-%d")
                                            fig_err = px.scatter(
                                                err_df,
                                                x="target_date",
                                                y="Error",
                                                color="Model",
                                                title="Prediction error over time (backtest windows)",
                                            )
                                            fig_err.update_layout(xaxis_title="Target date", yaxis_title="y_pred - y_true")
                                            st.plotly_chart(fig_err, use_container_width=True)
                                        else:
                                            st.caption("No error points to plot.")

                                    st.caption(
                                        "These predictions come from **backtest windows** on the offline demo dataset; "
                                        "they are not live trading signals."
                                    )

    except Exception as e:
        st.error("**Something went wrong on this page.**")
        st.code(str(e), language="text")
        st.caption("If this persists, check the browser console or restart the app.")
