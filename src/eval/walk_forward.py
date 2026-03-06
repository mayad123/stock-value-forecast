"""
Walk-forward (fold-based) backtesting.
Uses eval.min_train_days, eval.fold_size_days, eval.step_size_days to build folds.
Each fold has train range, test range, and per-model metrics. Outputs aggregate mean/std across folds.
"""

import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.core.artifacts import resolve_run_dir
from src.eval.baselines import get_baseline_predictions, list_baseline_names
from src.eval.metrics import compute_metrics

# Scalar metrics to aggregate with mean/std (exclude n_samples or handle separately)
SCALAR_METRIC_KEYS = ["mse", "rmse", "mae", "r2", "directional_accuracy", "ic"]


def _evaluate_tf(
    config: Dict[str, Any],
    models_path: Path,
    dataset_version: str,
    train_df: pd.DataFrame,
    test_window_df: pd.DataFrame,
    y_true: Any,
    log: Any,
) -> Optional[Dict[str, float]]:
    """Evaluate TensorFlow model on a test window; return metrics or None."""
    try:
        from src.train.load import load_trained_model, predict_with_trained_model
    except Exception:
        return None
    run_id_hint = config.get("eval", {}).get("tensorflow_run_id", "").strip() or None
    try:
        run_dir = resolve_run_dir(models_path, dataset_version, run_id_hint=run_id_hint)
    except FileNotFoundError:
        return None
    try:
        model, record = load_trained_model(run_dir)
        y_pred = predict_with_trained_model(model, record, test_window_df)
        return compute_metrics(y_true, y_pred)
    except Exception:
        return None


def _test_windows_by_dates(
    test_df: pd.DataFrame,
    fold_size_days: int,
    step_size_days: int,
    date_col: str = "date",
) -> List[Tuple[str, str, pd.DataFrame]]:
    """
    Split test_df into consecutive time windows. Returns list of (window_start, window_end, subset_df).
    """
    test_df = test_df.sort_values(date_col).drop_duplicates(subset=[date_col], keep="first")
    dates = sorted(test_df[date_col].astype(str).unique())
    if not dates:
        return []
    out = []
    start_idx = 0
    while start_idx < len(dates):
        end_idx = min(start_idx + fold_size_days, len(dates))
        window_dates = set(dates[start_idx:end_idx])
        subset = test_df[test_df[date_col].astype(str).isin(window_dates)]
        if len(subset) > 0:
            out.append((dates[start_idx], dates[end_idx - 1], subset))
        start_idx += step_size_days
        if start_idx >= len(dates):
            break
    return out


def _aggregate_across_folds(
    fold_results: List[Dict[str, Any]],
    model_names: List[str],
) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    Compute mean and std per model per metric across folds.
    Returns aggregate[model][metric] = {"mean": float, "std": float}.
    """
    aggregate: Dict[str, Dict[str, Dict[str, float]]] = {}
    for name in model_names:
        aggregate[name] = {}
        for key in SCALAR_METRIC_KEYS:
            values = []
            for fold in fold_results:
                m = (fold.get("metrics") or {}).get(name)
                if m is not None and key in m and isinstance(m[key], (int, float)) and not math.isnan(m[key]):
                    values.append(float(m[key]))
            if values:
                n = len(values)
                mean = sum(values) / n
                variance = sum((x - mean) ** 2 for x in values) / n if n > 0 else 0.0
                std = math.sqrt(variance) if n > 1 else 0.0
                aggregate[name][key] = {"mean": round(mean, 10), "std": round(std, 10)}
            else:
                aggregate[name][key] = {"mean": float("nan"), "std": float("nan")}
        # n_samples: report mean and std across folds
        n_vals = []
        for fold in fold_results:
            m = (fold.get("metrics") or {}).get(name)
            if m is not None and "n_samples" in m:
                n_vals.append(int(m["n_samples"]))
        if n_vals:
            mean_n = sum(n_vals) / len(n_vals)
            aggregate[name]["n_samples"] = {"mean": mean_n, "std": 0.0 if len(n_vals) == 1 else (sum((x - mean_n) ** 2 for x in n_vals) / len(n_vals)) ** 0.5}
        else:
            aggregate[name]["n_samples"] = {"mean": float("nan"), "std": float("nan")}
    return aggregate


def run_walk_forward(
    config: Dict[str, Any],
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    processed_path: Path,
    models_path: Path,
    dataset_version: str,
    feature_manifest: Dict[str, Any],
    log: Any,
) -> Dict[str, Any]:
    """
    Run walk-forward backtest: build folds from eval.min_train_days, fold_size_days, step_size_days.
    Each fold has train range, test range, and per-model metrics. Returns artifact with folds and
    aggregate (mean/std per model per metric).
    """
    eval_cfg = config.get("eval") or {}
    wf_cfg = eval_cfg.get("walk_forward") or {}
    fold_size_days = int(eval_cfg.get("fold_size_days") or wf_cfg.get("window_days") or 28)
    step_size_days = int(eval_cfg.get("step_size_days") or wf_cfg.get("step_days") or 28)
    min_train_days = int(eval_cfg.get("min_train_days", 0))

    windows = _test_windows_by_dates(test_df, fold_size_days, step_size_days)
    if not windows:
        log("No test windows; skipping walk-forward")
        return {
            "dataset_version": dataset_version,
            "setup": {},
            "folds": [],
            "windows": [],
            "aggregate": {},
            "aggregated_metrics": {},
            "predictions": [],
        }

    # Full chronological dataframe for expanding train
    full_df = pd.concat([train_df, test_df], ignore_index=True)
    full_df = full_df.sort_values("date").reset_index(drop=True)
    all_dates = sorted(full_df["date"].astype(str).unique())

    time_horizon = config.get("time_horizon", {})
    tickers = config.get("tickers", {}).get("symbols", [])

    setup = {
        "tickers": tickers,
        "dataset_version": dataset_version,
        "train_end": time_horizon.get("train_end"),
        "val_start": time_horizon.get("val_start"),
        "val_end": time_horizon.get("val_end"),
        "test_start": time_horizon.get("test_start"),
        "min_train_days": min_train_days,
        "fold_size_days": fold_size_days,
        "step_size_days": step_size_days,
        "n_windows": len(windows),
    }

    model_names = list_baseline_names() + ["tensorflow"]
    folds: List[Dict[str, Any]] = []
    window_results: List[Dict[str, Any]] = []
    all_y_true: List[float] = []
    all_y_pred: Dict[str, List[float]] = {n: [] for n in model_names}
    forward_days = int((config.get("feature_windows") or {}).get("forward_return_days", 1))
    predictions_list: List[Dict[str, Any]] = []

    def _target_date(asof: str, days: int) -> str:
        return (pd.to_datetime(asof) + pd.Timedelta(days=days)).strftime("%Y-%m-%d")

    for i, (test_start, test_end, subset) in enumerate(windows):
        # Train = all data before this test window start
        train_dates = [d for d in all_dates if d < test_start]
        if len(train_dates) < min_train_days:
            log(f"Fold {i+1}: skipping (train dates {len(train_dates)} < min_train_days {min_train_days})")
            continue
        train_start = train_dates[0]
        train_end = train_dates[-1]
        train_fold_df = full_df[full_df["date"].astype(str) < test_start].copy()

        y_true = subset["target_forward_return"].astype(float).values
        all_y_true.extend(y_true.tolist())

        fold_row: Dict[str, Any] = {
            "fold_id": i,
            "train_start": train_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            "n_samples": len(subset),
            "metrics": {},
        }
        window_row: Dict[str, Any] = {
            "window_start": test_start,
            "window_end": test_end,
            "n_samples": len(subset),
            "metrics": {},
        }
        fold_y_preds: Dict[str, Any] = {}

        for name in list_baseline_names():
            y_pred = get_baseline_predictions(name, train_fold_df, subset)
            m = compute_metrics(y_true, y_pred)
            fold_row["metrics"][name] = m
            window_row["metrics"][name] = m
            all_y_pred[name].extend(y_pred.tolist())
            fold_y_preds[name] = y_pred

        tf_m = _evaluate_tf(config, models_path, dataset_version, train_fold_df, subset, y_true, log)
        fold_row["metrics"]["tensorflow"] = tf_m
        window_row["metrics"]["tensorflow"] = tf_m
        if tf_m is not None:
            try:
                from src.train.load import load_trained_model, predict_with_trained_model
                run_id_hint = config.get("eval", {}).get("tensorflow_run_id", "").strip() or None
                run_dir = resolve_run_dir(models_path, dataset_version, run_id_hint=run_id_hint)
                model, record = load_trained_model(run_dir)
                y_pred_tf = predict_with_trained_model(model, record, subset)
                all_y_pred["tensorflow"].extend(y_pred_tf.tolist())
                fold_y_preds["tensorflow"] = y_pred_tf
            except (FileNotFoundError, Exception):
                fold_y_preds["tensorflow"] = None
        else:
            fold_y_preds["tensorflow"] = None

        for j in range(len(subset)):
            r = subset.iloc[j]
            asof_date = str(r["date"])
            target_date = _target_date(asof_date, forward_days)
            ticker = str(r["ticker"]) if "ticker" in subset.columns else ""
            y_true_j = float(r["target_forward_return"])
            for model_name, y_pred_arr in fold_y_preds.items():
                if y_pred_arr is not None and j < len(y_pred_arr):
                    p = float(y_pred_arr[j]) if hasattr(y_pred_arr[j], "__float__") else float(y_pred_arr[j])
                    predictions_list.append({
                        "ticker": ticker,
                        "asof_date": asof_date,
                        "target_date": target_date,
                        "y_true": y_true_j,
                        "y_pred": p,
                        "model_name": model_name,
                        "fold_id": i,
                    })

        folds.append(fold_row)
        window_results.append(window_row)
        log(f"Fold {i+1}/{len(windows)} train [{train_start} .. {train_end}] test [{test_start} .. {test_end}] n={len(subset)}")

    aggregate = _aggregate_across_folds(folds, model_names)

    # Pooled aggregated_metrics (all predictions concatenated) for backward compat
    aggregated_metrics: Dict[str, Any] = {}
    n_total = len(all_y_true)
    for name in model_names:
        preds = all_y_pred[name]
        if len(preds) == n_total:
            aggregated_metrics[name] = compute_metrics(all_y_true, preds)
        else:
            aggregated_metrics[name] = None

    return {
        "setup": setup,
        "folds": folds,
        "windows": window_results,
        "aggregate": aggregate,
        "aggregated_metrics": aggregated_metrics,
        "predictions": predictions_list,
        "run_timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
