"""
Isolated UI layer for Stock Value Forecast.
Requires the backend API (python run.py serve). Data from API and optional report files.
"""

import os
from pathlib import Path
from typing import Any

import plotly.express as px
import pandas as pd
import streamlit as st

import api_client
import data_access
import format as fmt

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_URL = (os.environ.get("BACKEND_URL") or "").strip() or None
_BACKEND_TIMEOUT = int(os.environ.get("BACKEND_TIMEOUT", "60"))
_METRICS_FILE_MISSING_MSG = (
    "Metrics file not found. Run a backtest to generate it (e.g. `make demo` or `python run.py backtest`). "
    "Expected: reports/latest_metrics.json."
)


def _backend_ok() -> bool:
    """True if backend is reachable. Cached in session_state."""
    if not _BACKEND_URL:
        st.session_state["backend_reachable"] = False
        return False
    if "backend_reachable" not in st.session_state:
        st.session_state["backend_reachable"] = api_client.get_health(_BACKEND_URL, _BACKEND_TIMEOUT)
    return st.session_state.get("backend_reachable", False)


def _get_prediction_options():
    """Prediction options from API. Cached in session_state. Sets prediction_options_error on failure."""
    if not _BACKEND_URL or not _backend_ok():
        st.session_state["prediction_options_error"] = "Backend not configured or unreachable. Set BACKEND_URL and run the API."
        return None
    if "prediction_options" not in st.session_state:
        data, err = api_client.get_prediction_options(_BACKEND_URL, _BACKEND_TIMEOUT)
        st.session_state["prediction_options"] = data
        st.session_state["prediction_options_error"] = err
    return st.session_state.get("prediction_options")


# ----- Page renderers -----


def _page_evaluation():
    """Evaluation: aggregate metrics, baseline vs model, fold stability, predictions. Data from API only."""
    st.header("Evaluation")
    st.markdown(
        "Aggregate backtest metrics, baseline vs model comparison, and walk-forward fold stability. "
        "All data is loaded from the backend API."
    )
    st.divider()

    metrics_data, metrics_error = api_client.get_metrics(_BACKEND_URL, _BACKEND_TIMEOUT)
    predictions_data, predictions_error = api_client.get_predictions(_BACKEND_URL, _BACKEND_TIMEOUT)
    if not metrics_error and not predictions_error:
        st.session_state["backend_reachable"] = True
    if metrics_error:
        st.session_state["backend_reachable"] = False

    if metrics_error:
        st.error("**Could not load metrics.** " + metrics_error)
        st.caption("Ensure the backend is running and a backtest has been run (e.g. `make demo`).")
        return
    if metrics_data is None:
        st.warning("No metrics data available.")
        return

    metrics_data = metrics_data or {}
    predictions_data = predictions_data or []
    if not isinstance(predictions_data, list):
        predictions_data = []
    models = (metrics_data or {}).get("models") or {}
    folds = (metrics_data or {}).get("folds") or []
    aggregate = (metrics_data or {}).get("aggregate") or {}

    def _safe_pred(p: Any) -> dict:
        return p if isinstance(p, dict) else {}
    preds = [_safe_pred(p) for p in predictions_data]
    tickers = sorted(set(p.get("ticker") for p in preds if p.get("ticker")))
    model_names = sorted(models.keys()) if models else sorted(set(p.get("model_name") for p in preds if p.get("model_name")))
    fold_ids = sorted(set(p.get("fold_id") for p in preds if p.get("fold_id") is not None))

    st.sidebar.markdown("**Filters**")
    filter_ticker = st.sidebar.multiselect("Ticker", options=["All"] + tickers, default=["All"], key="eval_ticker")
    filter_model = st.sidebar.multiselect("Model", options=["All"] + model_names, default=["All"], key="eval_model")
    filter_fold = st.sidebar.multiselect("Fold ID", options=["All"] + [str(i) for i in fold_ids], default=["All"], key="eval_fold")

    use_all_tickers = "All" in filter_ticker or not filter_ticker
    use_all_models = "All" in filter_model or not filter_model
    use_all_folds = "All" in filter_fold or not filter_fold
    selected_fold_ids = None if use_all_folds else [int(x) for x in filter_fold if x != "All" and x.isdigit()]
    model_filter = None if use_all_models else filter_model

    # Aggregate metrics table
    st.subheader("Aggregate metrics")
    if not models:
        st.info("No model metrics (run a backtest).")
    else:
        rows = fmt.metrics_table_rows(
            {n: m for n, m in models.items() if use_all_models or n in filter_model},
            ["mse", "rmse", "mae", "r2", "directional_accuracy", "n_samples"],
        )
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.caption("No models match the selected filter.")

    # Baseline vs model chart
    st.subheader("Baseline vs model comparison")
    if models:
        chart_data = fmt.metrics_chart_data(
            {n: m for n, m in models.items() if use_all_models or n in filter_model},
            ["mse", "mae", "directional_accuracy"],
        )
        if chart_data:
            fig = px.bar(chart_data, x="Model", y="Value", color="Model", facet_row="Metric", barmode="group", title="Metrics by model")
            fig.update_layout(showlegend=False)
            fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No plottable metrics.")

    # Fold stability
    st.subheader("Fold stability")
    folds_safe = [f if isinstance(f, dict) else {} for f in folds]
    folds_filtered = [f for f in folds_safe if use_all_folds or f.get("fold_id") in (selected_fold_ids or [])]
    if len(folds_safe) < 2:
        st.warning("Walk-forward needs at least 2 folds. Run a backtest with eval.fold_size_days and eval.step_size_days.")
        if folds_safe:
            st.dataframe(fmt.fold_table_rows(folds_safe), use_container_width=True, hide_index=True)
    else:
        st.dataframe(fmt.fold_table_rows(folds_filtered), use_container_width=True, hide_index=True)
        st.caption("Metrics per fold (by model)")
        per_fold = fmt.per_fold_metrics_rows(folds_filtered, ["mse", "mae", "directional_accuracy"], model_filter)
        if per_fold:
            st.dataframe(per_fold, use_container_width=True, hide_index=True)
        if aggregate and isinstance(aggregate, dict):
            st.caption("Aggregate (mean ± std across folds)")
            agg_rows = fmt.aggregate_mean_std_rows(aggregate, model_filter)
            if agg_rows:
                st.dataframe(agg_rows, use_container_width=True, hide_index=True)
        st.caption("Metric value by fold")
        chart_data = fmt.fold_chart_data(folds_filtered, ["mse", "mae", "directional_accuracy"], model_filter)
        if chart_data:
            fig = px.line(chart_data, x="Fold ID", y="Value", color="Model", facet_row="Metric", markers=True)
            fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
            st.plotly_chart(fig, use_container_width=True)

    # Filtered predictions table
    pred_filtered = list(preds)
    if not use_all_tickers and tickers:
        pred_filtered = [p for p in pred_filtered if p.get("ticker") in filter_ticker]
    if not use_all_models and model_names:
        pred_filtered = [p for p in pred_filtered if p.get("model_name") in filter_model]
    if not use_all_folds and selected_fold_ids is not None:
        pred_filtered = [p for p in pred_filtered if p.get("fold_id") in selected_fold_ids]

    st.subheader("Predictions")
    if predictions_error and not predictions_data:
        st.caption("Predictions could not be loaded: " + predictions_error)
    elif pred_filtered:
        st.dataframe(pred_filtered[:500], use_container_width=True, hide_index=True)
        if len(pred_filtered) > 500:
            st.caption(f"Showing first 500 of {len(pred_filtered)} rows.")
    else:
        st.caption("No prediction rows, or none match the current filters.")


def _page_model_overview():
    """Model Overview: metadata from API, metrics from file, feature importance from API."""
    st.header("Model Overview")
    st.markdown(
        "Shows the loaded model's version, dataset, feature schema, and aggregate backtest metrics. "
        "Supports reproducibility and evaluation rigor (baseline comparison)."
    )
    st.divider()

    model_info, model_info_error = api_client.get_model_info(_BACKEND_URL, _BACKEND_TIMEOUT)
    if model_info_error:
        st.session_state["backend_reachable"] = False

    metrics_data, metrics_error = data_access.load_metrics_file(_REPO_ROOT)
    if metrics_error and not _REPO_ROOT.joinpath("reports", "latest_metrics.json").exists():
        metrics_error = _METRICS_FILE_MISSING_MSG

    if model_info_error or metrics_error or not model_info or not isinstance(model_info, dict):
        st.error("**Model Overview is missing one or more data sources.**")
        if model_info_error:
            st.markdown(f"- **Backend (/model_info):** {model_info_error}")
        elif not model_info or not isinstance(model_info, dict):
            st.markdown("- **Backend (/model_info):** No valid data (backend may have returned empty or null).")
        if metrics_error:
            st.markdown(f"- **Metrics file:** {metrics_error}")
        st.markdown("Ensure the backend is running and a backtest has been run so that reports/latest_metrics.json exists.")
        return

    # Metadata
    st.subheader("Metadata")
    c1, c2, c3, c4 = st.columns(4)
    fp = (model_info or {}).get("feature_schema_fingerprint") or "—"
    fp_display = (fp[:16] + "…") if fp != "—" and len(fp) > 16 else fp
    with c1:
        st.metric("Model version", model_info.get("model_version", "—"))
    with c2:
        st.metric("Dataset version", model_info.get("dataset_version", "—"))
    with c3:
        st.metric("Number of features", model_info.get("num_features", "—"))
    with c4:
        st.metric("Schema fingerprint", fp_display)
    if model_info.get("training_window"):
        with st.expander("Training window"):
            st.json(model_info["training_window"])
    if model_info.get("feature_columns"):
        with st.expander("Feature columns"):
            st.write(", ".join(model_info["feature_columns"]))

    # Aggregate metrics
    st.subheader("Aggregate evaluation metrics")
    models = (metrics_data or {}).get("models") or {}
    if not models:
        st.info("No model metrics in latest_metrics.json (empty backtest?).")
    else:
        st.dataframe(fmt.metrics_table_rows(models, ["mse", "rmse", "mae", "r2", "directional_accuracy", "n_samples"]), use_container_width=True, hide_index=True)
        st.subheader("Baseline vs model comparison")
        chart_data = fmt.metrics_chart_data(models, ["mse", "mae", "directional_accuracy"])
        if chart_data:
            fig = px.bar(chart_data, x="Model", y="Value", color="Model", facet_row="Metric", barmode="group", title="Metrics by model (MSE, MAE, directional accuracy)")
            fig.update_layout(showlegend=False)
            fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No plottable metrics (all NaN or missing).")

    # Feature importance (API)
    st.subheader("Feature importance")
    fi_data, fi_error = api_client.get_feature_importance(_BACKEND_URL, _BACKEND_TIMEOUT)
    if fi_data and fi_data.get("feature_importance"):
        fi_df = pd.DataFrame(fi_data["feature_importance"])
        fig_fi = px.bar(
            fi_df, y="feature", x="importance",
            error_x="std" if "std" in fi_df.columns and fi_df["std"].fillna(0).any() else None,
            orientation="h",
            labels={"importance": "Permutation importance (MSE increase)", "feature": "Feature"},
            title="Permutation-based feature importance",
        )
        fig_fi.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig_fi, use_container_width=True)
        st.caption(f"Based on {fi_data.get('n_eval_samples', '—')} samples, {fi_data.get('n_repeats', 5)} permutations per feature. Run `python run.py feature-importance` to regenerate.")
    elif fi_error:
        st.caption("Could not load feature importance from backend.")
    else:
        st.caption("Feature importance not generated yet. Run `python run.py feature-importance` to produce it.")


def _page_prediction_explorer():
    """Prediction Explorer: single prediction form, options from API."""
    st.header("Prediction Explorer")
    st.markdown(
        "Run a single prediction for a ticker and as-of date. Choices are limited to tickers, dates, and horizons that exist in the processed data."
    )
    st.divider()

    opts = _get_prediction_options()
    if not opts or not isinstance(opts, dict) or not opts.get("tickers") or not opts.get("dates_by_ticker"):
        err = st.session_state.get("prediction_options_error") or "Ensure the backend is running and supports `/prediction_options`, and that processed data exists."
        st.info(err)
        st.caption("Click **Recheck backend** in the sidebar and try again.")
        return

    dates_by_ticker = (opts.get("dates_by_ticker") or {}) if isinstance(opts.get("dates_by_ticker"), dict) else {}
    tickers = [t for t in (opts.get("tickers") or []) if dates_by_ticker.get(t)]
    horizons = opts.get("horizons") or [1]
    if not tickers:
        st.info("No tickers with processed data available.")
        return

    with st.form("predict_form"):
        ticker = st.selectbox("Ticker", options=tickers, key="pex_ticker")
        dates_for_ticker = dates_by_ticker.get(ticker, [])
        as_of = st.selectbox("Date", options=dates_for_ticker, key="pex_date") if dates_for_ticker else None
        horizon = st.selectbox("Horizon (days)", options=horizons, key="pex_horizon")
        submitted = st.form_submit_button("Get prediction")

    if submitted and as_of:
        data, err = api_client.post_predict(_BACKEND_URL, ticker, as_of, horizon, timeout=_BACKEND_TIMEOUT)
        if err:
            st.session_state["backend_reachable"] = False
            st.error("**Backend returned an error.** " + (err[:300] if isinstance(err, str) else str(err)[:300]))
            st.caption("Check that ticker and date exist in processed data.")
            return
        data = data if isinstance(data, dict) else {}
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


def _page_fold_stability():
    """Fold Stability: per-fold tables and charts from metrics file."""
    st.header("Fold Stability")
    st.markdown("Per-fold train/test ranges, metrics per model per fold, aggregate mean ± std, and metric variability chart.")
    st.divider()

    metrics_data, err = data_access.load_metrics_file(_REPO_ROOT)
    if err:
        st.error("**Metrics file not found.**")
        st.markdown(_METRICS_FILE_MISSING_MSG)
        st.markdown("For fold data, use a config with walk-forward enabled (eval.fold_size_days, eval.step_size_days).")
        return

    folds = (metrics_data or {}).get("folds") or []
    aggregate = (metrics_data or {}).get("aggregate") or {}

    if len(folds) < 2:
        st.warning("Walk-forward requires multiple folds. Run a backtest with walk-forward config to get at least 2 folds.")
        if folds:
            st.dataframe(fmt.fold_table_rows(folds), use_container_width=True, hide_index=True)
        return

    st.subheader("Folds")
    st.dataframe(fmt.fold_table_rows(folds), use_container_width=True, hide_index=True)
    st.subheader("Metrics per fold (by model)")
    per_fold = fmt.per_fold_metrics_rows(folds, ["mse", "mae", "directional_accuracy"])
    if per_fold:
        st.dataframe(per_fold, use_container_width=True, hide_index=True)
    else:
        st.info("No per-fold metrics in file.")
    st.subheader("Aggregate (mean ± std across folds)")
    if aggregate:
        agg_rows = fmt.aggregate_mean_std_rows(aggregate)
        if agg_rows:
            st.dataframe(agg_rows, use_container_width=True, hide_index=True)
        else:
            st.info("No aggregate mean/std in file.")
    else:
        st.info("No aggregate block in file.")
    st.subheader("Fold metric variability")
    chart_data = fmt.fold_chart_data(folds, ["mse", "mae", "directional_accuracy"])
    if chart_data:
        fig = px.line(chart_data, x="Fold ID", y="Value", color="Model", facet_row="Metric", markers=True, title="Metric value by fold (variability across folds)")
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No plottable per-fold metrics.")


def _page_price_overlay():
    """Price + Backtest Overlay: predictions vs historical prices from API."""
    st.header("Price + Backtest Overlay")
    st.markdown("Visualize backtest-window predictions against historical prices for a selected ticker. For recruiter intuition, not live trading.")
    st.divider()

    predictions_data, predictions_error = api_client.get_predictions(_BACKEND_URL, _BACKEND_TIMEOUT)
    if predictions_error:
        st.error("**Could not load predictions.** " + predictions_error)
        st.caption("Ensure the backend is running and a backtest has been run (e.g. make demo or python run.py demo-real).")
        return
    if not predictions_data:
        st.info("No predictions available. Run a backtest first.")
        return

    predictions_data = [p for p in (predictions_data or []) if isinstance(p, dict)]
    if not predictions_data:
        st.info("No valid prediction rows.")
        return
    pred_df = pd.DataFrame(predictions_data)
    if "ticker" not in pred_df.columns or "target_date" not in pred_df.columns:
        st.error("Predictions payload missing required columns.")
        return

    pred_df["ticker"] = pred_df["ticker"].astype(str)
    pred_df["target_date"] = pd.to_datetime(pred_df["target_date"])
    tickers = sorted(pred_df["ticker"].unique())
    model_names = sorted(pred_df["model_name"].unique()) if "model_name" in pred_df.columns else []

    c1, c2 = st.columns([1, 1])
    with c1:
        sel_ticker = st.selectbox("Ticker", options=tickers, index=0)
    with c2:
        sel_models = st.multiselect("Models (backtest)", options=model_names, default=model_names)

    pred_t = pred_df[pred_df["ticker"] == sel_ticker]
    if sel_models:
        pred_t = pred_t[pred_t["model_name"].isin(sel_models)]
    if pred_t.empty:
        st.info("No prediction rows for this ticker / model selection.")
        return

    min_date = pred_t["target_date"].min().strftime("%Y-%m-%d")
    max_date = pred_t["target_date"].max().strftime("%Y-%m-%d")

    prices_data, prices_error = api_client.get_prices(_BACKEND_URL, sel_ticker, start_date=min_date, end_date=max_date, timeout=_BACKEND_TIMEOUT)
    if prices_error:
        st.error("**Could not load prices.** " + prices_error)
        return
    if not prices_data:
        st.info("No price data available for this ticker and date range.")
        return

    prices_df = pd.DataFrame(prices_data)
    if "date" not in prices_df.columns:
        st.error("Price payload missing 'date' column.")
        return

    prices_df["date"] = pd.to_datetime(prices_df["date"])
    price_col = next((c for c in ["adjusted_close", "close"] if c in prices_df.columns), None)
    if not price_col:
        st.error("Price payload missing adjusted_close/close columns.")
        return
    prices_df = prices_df.sort_values("date")

    st.subheader(f"Price for {sel_ticker}")
    fig_price = px.line(prices_df, x="date", y=price_col, title=f"{sel_ticker} price (demo dataset)")
    fig_price.update_layout(xaxis_title="Date", yaxis_title=price_col)
    st.plotly_chart(fig_price, use_container_width=True)

    st.subheader("Backtest predictions vs actual target")
    pred_plot = pred_t.copy()
    pred_plot["target_date"] = pred_plot["target_date"].dt.strftime("%Y-%m-%d")
    series_rows = []
    for _, row in pred_plot.iterrows():
        td = row["target_date"]
        if "y_true" in row and not pd.isna(row["y_true"]):
            series_rows.append({"target_date": td, "value": float(row["y_true"]), "Series": "Actual (y_true)"})
        if "y_pred" in row and not pd.isna(row["y_pred"]):
            series_rows.append({"target_date": td, "value": float(row["y_pred"]), "Series": f"Pred ({row['model_name']})"})
    if series_rows:
        series_df = pd.DataFrame(series_rows)
        fig_pred = px.line(series_df, x="target_date", y="value", color="Series", markers=True, title="Predicted vs actual forward return (backtest windows)")
        fig_pred.update_layout(xaxis_title="Target date", yaxis_title="Forward return")
        st.plotly_chart(fig_pred, use_container_width=True)
    else:
        st.caption("No plottable prediction series.")

    if "y_true" in pred_t.columns and "y_pred" in pred_t.columns:
        st.subheader("Prediction error (y_pred - y_true)")
        err_rows = [{"target_date": row["target_date"], "Error": float(row["y_pred"] - row["y_true"]), "Model": row.get("model_name")}
                    for _, row in pred_t.iterrows() if not pd.isna(row.get("y_true")) and not pd.isna(row.get("y_pred"))]
        if err_rows:
            err_df = pd.DataFrame(err_rows)
            err_df["target_date"] = err_df["target_date"].dt.strftime("%Y-%m-%d")
            fig_err = px.scatter(err_df, x="target_date", y="Error", color="Model", title="Prediction error over time (backtest windows)")
            fig_err.update_layout(xaxis_title="Target date", yaxis_title="y_pred - y_true")
            st.plotly_chart(fig_err, use_container_width=True)
    st.caption("These predictions come from backtest windows on the offline demo dataset; they are not live trading signals.")


def _sidebar_try_it():
    """Sidebar expander: single prediction (Try It)."""
    opts = _get_prediction_options()
    if not opts or not isinstance(opts, dict) or not opts.get("tickers") or not opts.get("dates_by_ticker"):
        err = st.session_state.get("prediction_options_error") or "Ensure the backend is running and supports `/prediction_options`, and that processed data exists."
        st.caption(err)
        st.caption("Click **Recheck backend** and try again.")
        return

    dates_by_ticker = (opts.get("dates_by_ticker") or {}) if isinstance(opts.get("dates_by_ticker"), dict) else {}
    tickers = [t for t in (opts.get("tickers") or []) if dates_by_ticker.get(t)]
    horizons = opts.get("horizons") or [1]
    if not tickers:
        st.caption("No tickers with processed data available.")
        return

    tryit_ticker = st.selectbox("Ticker", options=tickers, key="tryit_ticker")
    dates_for_ticker = dates_by_ticker.get(tryit_ticker, [])
    tryit_date = st.selectbox("Date", options=dates_for_ticker, key="tryit_date") if dates_for_ticker else None
    tryit_horizon = st.selectbox("Horizon (days)", options=horizons, key="tryit_horizon")
    tryit_clicked = st.button("Get prediction", key="tryit_btn")

    if tryit_clicked and tryit_date:
        data, err = api_client.post_predict(_BACKEND_URL, tryit_ticker, tryit_date, tryit_horizon, timeout=_BACKEND_TIMEOUT)
        if err:
            st.error("Error: " + (err[:300] if isinstance(err, str) else str(err)[:300]))
            return
        data = data if isinstance(data, dict) else {}
        pred_val = data.get("prediction")
        model_version = data.get("model_version") or "—"
        price_current = None
        prices_data, _ = api_client.get_prices(_BACKEND_URL, tryit_ticker, end_date=tryit_date, timeout=_BACKEND_TIMEOUT)
        if prices_data and len(prices_data) > 0:
            last = prices_data[-1]
            last = last if isinstance(last, dict) else {}
            price_current = float(last.get("adjusted_close") or last.get("close") or 0)
        info_data, _ = api_client.get_model_info(_BACKEND_URL, _BACKEND_TIMEOUT)
        info_data = info_data if isinstance(info_data, dict) else {}
        dataset_version = info_data.get("dataset_version", "—")
        st.success("Prediction received.")
        price_next = None
        if isinstance(pred_val, (int, float)) and price_current is not None:
            try:
                price_next = price_current * (1.0 + float(pred_val))
            except Exception:
                pass
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Current price", f"{price_current:,.2f}" if price_current is not None else "N/A")
            st.metric("Predicted 1-day simple return", f"{float(pred_val) * 100:.2f}%" if isinstance(pred_val, (int, float)) else "N/A")
        with c2:
            st.metric("Implied next-day price", f"{price_next:,.2f}" if price_next is not None else "N/A")
            st.caption(f"Model version: {model_version}")
            st.caption(f"Dataset version: {dataset_version}")


# ----- App entry -----

st.set_page_config(page_title="Stock Value Forecast — Evaluation", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

st.sidebar.title("Stock Value Forecast")
st.sidebar.caption("ML evaluation & serving")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigate",
    options=["Evaluation", "Model Overview", "Prediction Explorer", "Fold Stability", "Price + Backtest Overlay"],
    index=0,
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
if st.sidebar.button("Recheck backend"):
    for key in ("backend_reachable", "prediction_options", "prediction_options_error"):
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()
st.sidebar.caption("Backend: `python run.py serve`")

if _BACKEND_URL:
    with st.sidebar.expander("Try It — single prediction"):
        _sidebar_try_it()

if not _BACKEND_URL:
    st.error("**Backend configuration required.** Set the `BACKEND_URL` environment variable to the running API, e.g. `BACKEND_URL=http://localhost:8000`")
    st.markdown("Start the backend with `python run.py serve`, then launch Streamlit with `BACKEND_URL=http://localhost:8000 streamlit run frontend/app.py`.")
else:
    backend_ok = _backend_ok()
    if not backend_ok:
        st.warning("**Backend is unreachable.** Start it with: `python run.py serve` (expected: BACKEND_URL=" + _BACKEND_URL + ")")

    try:
        if page == "Evaluation":
            _page_evaluation()
        elif page == "Model Overview":
            _page_model_overview()
        elif page == "Prediction Explorer":
            _page_prediction_explorer()
        elif page == "Fold Stability":
            _page_fold_stability()
        elif page == "Price + Backtest Overlay":
            _page_price_overlay()
    except Exception as e:
        st.error("**Something went wrong on this page.**")
        st.code(str(e), language="text")
        st.caption("If this persists, check the browser console or restart the app.")
