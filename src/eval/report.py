"""
Generate human-readable backtest reports. Single-window and walk-forward artifacts supported.
Deterministic: same artifact -> same report.
"""

import math
from pathlib import Path
from typing import Any, Dict, Union


def generate_single_window_report(summary: Dict[str, Any]) -> str:
    """
    Generate Markdown report from a single-window backtest summary.
    Summary must have: dataset_version, models (name -> metrics dict).
    Optional: train_end, val_start, val_end, test_start, n_test.
    Includes: dataset version, split boundaries / eval window, metrics per model, notes.
    """
    lines = [
        "# Backtest Report",
        "",
        "## Dataset version",
        "",
        f"- **Processed dataset version:** {summary.get('dataset_version', '—')}",
        "",
        "## Split boundaries / evaluation window",
        "",
        f"- **Train end:** {summary.get('train_end', '—')}",
        f"- **Val start:** {summary.get('val_start', '—')}",
        f"- **Val end:** {summary.get('val_end', '—')}",
        f"- **Test start:** {summary.get('test_start', '—')}",
        f"- **Test samples:** {summary.get('n_test', '—')}",
        "",
        "## Metrics (per model)",
        "",
        "| Model | MSE | RMSE | MAE | R² | Dir. accuracy | n_samples |",
        "|-------|-----|------|-----|-----|----------------|-----------|",
    ]
    models = summary.get("models") or {}
    for name in ["naive", "heuristic", "simple_ml", "tensorflow"]:
        m = models.get(name)
        if m is None:
            lines.append(f"| {name} | — | — | — | — | — | — |")
        else:
            lines.append(
                f"| {name} | {m.get('mse', '—')} | {m.get('rmse', '—')} | {m.get('mae', '—')} | "
                f"{m.get('r2', '—')} | {m.get('directional_accuracy', '—')} | {m.get('n_samples', '—')} |"
            )
    lines.extend([
        "",
        "## Notes",
        "",
        "Single-window backtest. Baselines and (if available) the trained TensorFlow model "
        "were evaluated on the test split. Metrics are computed on the same test set for comparison.",
        "",
        "*Report generated from backtest run (deterministic).*",
    ])
    return "\n".join(lines)


def _fmt_metrics(m: Dict[str, Any]) -> str:
    if not m:
        return "—"
    return " | ".join(f"{k}: {v}" for k, v in m.items() if k != "n_samples")


def generate_report(
    artifact: Union[Path, str, Dict[str, Any]],
    out_path: Union[Path, str, None] = None,
) -> str:
    """
    Generate Markdown report from backtest artifact (path to backtest_run.json or dict).
    If out_path is set, write to file; return report string.
    """
    if isinstance(artifact, (Path, str)):
        path = Path(artifact)
        with open(path) as f:
            import json
            data = json.load(f)
    else:
        data = artifact

    setup = data.get("setup", {})
    windows = data.get("windows", [])
    folds = data.get("folds", []) or windows  # fallback to windows for legacy
    agg = data.get("aggregated_metrics", {})
    agg_mean_std = data.get("aggregate", {})

    lines = [
        "# Backtest Report",
        "",
        "## 1. Setup",
        "",
        f"- **Tickers:** {', '.join(str(t) for t in (setup.get('tickers') or [])) or '—'}",
        f"- **Dataset version:** {setup.get('dataset_version', '—')}",
        f"- **Train end:** {setup.get('train_end', '—')}",
        f"- **Val window:** {setup.get('val_start', '—')} .. {setup.get('val_end', '—')}",
        f"- **Test start:** {setup.get('test_start', '—')}",
        f"- **Folds:** min_train_days={setup.get('min_train_days', '—')}, fold_size={setup.get('fold_size_days', setup.get('window_days', '—'))} days, step={setup.get('step_size_days', setup.get('step_days', '—'))} days",
        f"- **Number of folds:** {len(folds)}",
        "",
    ]

    # 2. Fold ranges (train/test dates per fold)
    lines.extend(["## 2. Fold ranges (train / test dates)", ""])
    if not folds:
        lines.append("No fold data.")
    else:
        lines.append("| Fold | Train start | Train end | Test start | Test end | n_samples |")
        lines.append("|------|-------------|-----------|------------|----------|-----------|")
        for f in folds:
            tid = f.get("fold_id", 0)
            ts = f.get("train_start", f.get("window_start", "—"))
            te = f.get("train_end", "—")
            if te == "—" and "window_start" in f:
                te = f.get("window_start", "—")
            tst_s = f.get("test_start", f.get("window_start", "—"))
            tst_e = f.get("test_end", f.get("window_end", "—"))
            n = f.get("n_samples", 0)
            lines.append(f"| {tid} | {ts} | {te} | {tst_s} | {tst_e} | {n} |")
    lines.extend(["", "## 3. Aggregate comparisons (mean ± std across folds)", ""])

    if agg_mean_std:
        def _fmt_mean_std(d: Dict[str, Any]) -> str:
            if not d:
                return "—"
            m, s = d.get("mean"), d.get("std")
            if m is None or (isinstance(m, float) and math.isnan(m)):
                return "—"
            if s is None or s == 0 or (isinstance(s, float) and math.isnan(s)):
                return str(m)
            return f"{m} ± {s}"

        lines.append("| Model | MSE | RMSE | MAE | R² | Dir. accuracy |")
        lines.append("|-------|-----|------|-----|-----|----------------|")
        for name in ["naive", "heuristic", "simple_ml", "tensorflow"]:
            row = agg_mean_std.get(name) or {}
            lines.append(
                f"| {name} | {_fmt_mean_std(row.get('mse'))} | {_fmt_mean_std(row.get('rmse'))} | {_fmt_mean_std(row.get('mae'))} | "
                f"{_fmt_mean_std(row.get('r2'))} | {_fmt_mean_std(row.get('directional_accuracy'))} |"
            )
    else:
        lines.append("(No aggregate mean/std; using pooled metrics below.)")
    lines.extend(["", "## 4. Pooled metrics (all folds concatenated)", ""])
    lines.append("| Model | MSE | RMSE | MAE | R² | Dir. accuracy |")
    lines.append("|-------|-----|------|-----|-----|----------------|")
    for name in ["naive", "heuristic", "simple_ml"]:
        m = agg.get(name)
        if m:
            lines.append(f"| {name} | {m.get('mse', '—')} | {m.get('rmse', '—')} | {m.get('mae', '—')} | {m.get('r2', '—')} | {m.get('directional_accuracy', '—')} |")
        else:
            lines.append(f"| {name} | — | — | — | — | — |")
    lines.extend(["", "## 5. TensorFlow model performance (pooled)", ""])
    tf_m = agg.get("tensorflow")
    if tf_m:
        lines.append(f"- **MSE:** {tf_m.get('mse', '—')}")
        lines.append(f"- **RMSE:** {tf_m.get('rmse', '—')}")
        lines.append(f"- **MAE:** {tf_m.get('mae', '—')}")
        lines.append(f"- **R²:** {tf_m.get('r2', '—')}")
        lines.append(f"- **Directional accuracy:** {tf_m.get('directional_accuracy', '—')}")
        lines.append(f"- **Samples:** {tf_m.get('n_samples', '—')}")
    else:
        lines.append("No TensorFlow model metrics (model not run or not available).")
    lines.append("")

    lines.extend(["## 6. Error analysis", ""])
    if not windows:
        lines.append("No per-window data.")
    else:
        worst = []
        for i, w in enumerate(windows):
            for model_name, m in (w.get("metrics") or {}).items():
                if m and "mse" in m:
                    worst.append((i, w.get("window_start", ""), w.get("window_end", ""), model_name, m["mse"], m.get("directional_accuracy")))
        worst.sort(key=lambda x: x[4], reverse=True)
        lines.append("**Worst windows by MSE (top 5):**")
        lines.append("")
        for i, (idx, start, end, model, mse, acc) in enumerate(worst[:5]):
            lines.append(f"- Window {idx+1} [{start} .. {end}], model={model}: MSE={mse}, dir_acc={acc}")
        lines.append("")
        lines.append("**Per-window sample counts:**")
        for i, w in enumerate(windows):
            lines.append(f"- Window {i+1} [{w.get('window_start')} .. {w.get('window_end')}]: n={w.get('n_samples', 0)}")
    lines.extend([
        "",
        "## Notes",
        "",
        "Walk-forward backtest. Baselines and (if available) the TensorFlow model were evaluated "
        "on each rolling test window; reported metrics are aggregated across windows.",
        "",
        "*Report generated from stored backtest artifact (deterministic).*",
    ])

    report = "\n".join(lines)
    if out_path is not None:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(report, encoding="utf-8")
    return report
