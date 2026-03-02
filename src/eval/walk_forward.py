"""
Walk-forward (rolling or fixed-size) backtesting.
Iterates through time windows, evaluates baselines and TensorFlow model consistently,
produces a stored artifact for deterministic report generation.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.eval.baselines import get_baseline_predictions, list_baseline_names
from src.eval.metrics import compute_metrics


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
    run_id = config.get("eval", {}).get("tensorflow_run_id", "").strip() or None
    if run_id:
        run_dir = models_path / run_id
    else:
        candidates = [d.name for d in models_path.iterdir() if d.is_dir() and d.name.startswith(dataset_version + "_")]
        if not candidates:
            return None
        run_dir = models_path / sorted(candidates)[-1]
    has_model = (run_dir / "model.keras").exists() or (run_dir / "saved_model").exists()
    if not has_model or not (run_dir / "run_record.json").exists():
        return None
    try:
        model, record = load_trained_model(run_dir)
        y_pred = predict_with_trained_model(model, record, test_window_df)
        return compute_metrics(y_true, y_pred)
    except Exception:
        return None


def _test_windows_by_dates(
    test_df: pd.DataFrame,
    window_days: int,
    step_days: int,
    date_col: str = "date",
) -> List[Tuple[str, str, pd.DataFrame]]:
    """
    Split test_df into consecutive time windows. Returns list of (window_start, window_end, subset_df).
    Dates are strings YYYY-MM-DD; windows are inclusive [start, end] by unique dates.
    """
    test_df = test_df.sort_values(date_col).drop_duplicates(subset=[date_col], keep="first")
    dates = sorted(test_df[date_col].astype(str).unique())
    if not dates:
        return []
    out = []
    start_idx = 0
    while start_idx < len(dates):
        end_idx = min(start_idx + window_days, len(dates))
        window_dates = set(dates[start_idx:end_idx])
        subset = test_df[test_df[date_col].astype(str).isin(window_dates)]
        if len(subset) > 0:
            out.append((dates[start_idx], dates[end_idx - 1], subset))
        start_idx += step_days
        if start_idx >= len(dates):
            break
    return out


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
    Run walk-forward backtest: iterate through time windows, evaluate all models per window,
    aggregate metrics. Returns artifact dict (setup, windows, aggregated_metrics) for report.
    """
    wf_cfg = config.get("eval", {}).get("walk_forward", {})
    window_days = int(wf_cfg.get("window_days", 28))
    step_days = int(wf_cfg.get("step_days", 28))

    windows = _test_windows_by_dates(test_df, window_days, step_days)
    if not windows:
        log("No test windows; skipping walk-forward")
        return {"dataset_version": dataset_version, "windows": [], "aggregated_metrics": {}}

    time_horizon = config.get("time_horizon", {})
    tickers = config.get("tickers", {}).get("symbols", [])

    setup = {
        "tickers": tickers,
        "dataset_version": dataset_version,
        "train_end": time_horizon.get("train_end"),
        "val_start": time_horizon.get("val_start"),
        "val_end": time_horizon.get("val_end"),
        "test_start": time_horizon.get("test_start"),
        "window_days": window_days,
        "step_days": step_days,
        "n_windows": len(windows),
    }

    window_results: List[Dict[str, Any]] = []
    all_y_true: List[float] = []
    all_y_pred: Dict[str, List[float]] = {n: [] for n in list_baseline_names() + ["tensorflow"]}

    for i, (w_start, w_end, subset) in enumerate(windows):
        y_true = subset["target_forward_return"].astype(float).values
        all_y_true.extend(y_true.tolist())
        row: Dict[str, Any] = {"window_start": w_start, "window_end": w_end, "n_samples": len(subset), "metrics": {}}

        for name in list_baseline_names():
            y_pred = get_baseline_predictions(name, train_df, subset)
            m = compute_metrics(y_true, y_pred)
            row["metrics"][name] = m
            all_y_pred[name].extend(y_pred.tolist())

        tf_m = _evaluate_tf(config, models_path, dataset_version, train_df, subset, y_true, log)
        row["metrics"]["tensorflow"] = tf_m
        if tf_m is not None:
            try:
                from src.train.load import load_trained_model, predict_with_trained_model
                run_id = config.get("eval", {}).get("tensorflow_run_id", "").strip() or None
                if not run_id:
                    candidates = [d.name for d in models_path.iterdir() if d.is_dir() and d.name.startswith(dataset_version + "_")]
                    run_id = sorted(candidates)[-1] if candidates else None
                if run_id:
                    model, record = load_trained_model(models_path / run_id)
                    y_pred_tf = predict_with_trained_model(model, record, subset)
                    all_y_pred["tensorflow"].extend(y_pred_tf.tolist())
            except Exception:
                pass  # leave TF preds shorter; aggregate will be None
        # do not pad all_y_pred["tensorflow"] so aggregated is only set when we have full length

        window_results.append(row)
        log(f"Window {i+1}/{len(windows)} [{w_start} .. {w_end}]: n={len(subset)}")

    aggregated_metrics: Dict[str, Any] = {}
    n_total = len(all_y_true)
    for name in list_baseline_names() + ["tensorflow"]:
        preds = all_y_pred[name]
        if len(preds) == n_total:
            aggregated_metrics[name] = compute_metrics(all_y_true, preds)
        else:
            aggregated_metrics[name] = None

    return {
        "setup": setup,
        "windows": window_results,
        "aggregated_metrics": aggregated_metrics,
        "run_timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
