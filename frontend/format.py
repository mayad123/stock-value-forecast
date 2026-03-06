"""
Formatting and transformation helpers for display.

Pure functions: metrics tables, chart data, fold rows, etc. No Streamlit.
"""

import math
from typing import Any, Dict, List, Optional


def format_metric_value(v: Any) -> Any:
    """Display value for a metric: round float, or 'N/A' for None/NaN."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "N/A"
    if isinstance(v, (int, float)):
        return round(float(v), 6)
    return v


def metrics_table_rows(models: Dict[str, Any], metric_keys: List[str]) -> List[Dict[str, Any]]:
    """Build rows for a metrics dataframe: one row per model, columns Model + metric_keys."""
    rows = []
    for name, m in (models or {}).items():
        m = m if isinstance(m, dict) else {}
        row = {"Model": name}
        for k in metric_keys:
            row[k] = format_metric_value(m.get(k))
        rows.append(row)
    return rows


def metrics_chart_data(models: Dict[str, Any], chart_metrics: List[str]) -> List[Dict[str, Any]]:
    """Long-format data for Plotly bar chart: Model, Metric, Value."""
    out = []
    for model_name, m in (models or {}).items():
        m = m if isinstance(m, dict) else {}
        for mk in chart_metrics:
            v = m.get(mk)
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                out.append({"Model": model_name, "Metric": mk, "Value": float(v)})
    return out


def fold_table_rows(folds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rows for fold summary table: Fold ID, Train start/end, Test start/end, n_samples."""
    rows = []
    for idx, f in enumerate(folds or []):
        f = f if isinstance(f, dict) else {}
        rows.append({
            "Fold ID": f.get("fold_id", idx),
            "Train start": f.get("train_start", "—"),
            "Train end": f.get("train_end", "—"),
            "Test start": f.get("test_start", "—"),
            "Test end": f.get("test_end", "—"),
            "n_samples": f.get("n_samples", "—"),
        })
    return rows


def per_fold_metrics_rows(
    folds: List[Dict[str, Any]],
    metric_keys: List[str],
    model_filter: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Long-format rows: Fold ID, Model, then each metric. model_filter: include only these models (None = all)."""
    rows = []
    for idx, f in enumerate(folds or []):
        f = f if isinstance(f, dict) else {}
        fid = f.get("fold_id", idx)
        for model_name, m in (f.get("metrics") or {}).items():
            m = m if isinstance(m, dict) else {}
            if model_filter is not None and model_name not in model_filter:
                continue
            row = {"Fold ID": fid, "Model": model_name}
            for k in metric_keys:
                row[k] = format_metric_value(m.get(k))
            rows.append(row)
    return rows


def aggregate_mean_std_rows(
    aggregate: Dict[str, Any],
    model_filter: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Rows for aggregate mean ± std: Model, Metric, Mean, Std. model_filter: None = all."""
    rows = []
    for model_name, metrics in (aggregate or {}).items():
        if model_filter is not None and model_name not in model_filter:
            continue
        for metric_key, stats in (metrics or {}).items():
            if isinstance(stats, dict) and "mean" in stats and "std" in stats:
                mean_v, std_v = stats["mean"], stats["std"]
                if mean_v is None or std_v is None:
                    continue
                if isinstance(mean_v, float) and math.isnan(mean_v):
                    continue
                if isinstance(std_v, float) and math.isnan(std_v):
                    continue
                try:
                    mean_rounded = round(float(mean_v), 6)
                    std_rounded = round(float(std_v), 6)
                except (TypeError, ValueError):
                    continue
                rows.append({
                    "Model": model_name,
                    "Metric": metric_key,
                    "Mean": mean_rounded,
                    "Std": std_rounded,
                })
    return rows


def fold_chart_data(
    folds: List[Dict[str, Any]],
    chart_metrics: List[str],
    model_filter: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Long-format for Plotly line chart: Fold ID, Model, Metric, Value."""
    out = []
    for f in (folds or []):
        f = f if isinstance(f, dict) else {}
        fid = f.get("fold_id")
        for model_name, m in (f.get("metrics") or {}).items():
            m = m if isinstance(m, dict) else {}
            if model_filter is not None and model_name not in model_filter:
                continue
            for mk in chart_metrics:
                v = m.get(mk)
                if v is not None and not (isinstance(v, float) and math.isnan(v)):
                    out.append({"Fold ID": fid, "Model": model_name, "Metric": mk, "Value": float(v)})
    return out
