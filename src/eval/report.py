"""
Generate a human-readable backtest report from a stored backtest artifact.
Deterministic: same artifact -> same report.
"""

from pathlib import Path
from typing import Any, Dict, Union


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
    agg = data.get("aggregated_metrics", {})

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
        f"- **Walk-forward:** window={setup.get('window_days', '—')} days, step={setup.get('step_days', '—')} days",
        f"- **Windows:** {setup.get('n_windows', 0)}",
        "",
        "## 2. Baseline comparisons (aggregated)",
        "",
        "| Model | MSE | RMSE | MAE | R² | Dir. accuracy |",
        "|-------|-----|------|-----|-----|----------------|",
    ]

    for name in ["naive", "heuristic", "simple_ml"]:
        m = agg.get(name)
        if m:
            lines.append(f"| {name} | {m.get('mse', '—')} | {m.get('rmse', '—')} | {m.get('mae', '—')} | {m.get('r2', '—')} | {m.get('directional_accuracy', '—')} |")
        else:
            lines.append(f"| {name} | — | — | — | — | — |")

    lines.extend([
        "",
        "## 3. TensorFlow model performance",
        "",
    ])
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

    lines.extend([
        "## 4. Error analysis",
        "",
    ])
    if not windows:
        lines.append("No per-window data.")
    else:
        # Worst windows by MSE (across models)
        worst = []
        for i, w in enumerate(windows):
            for model_name, m in (w.get("metrics") or {}).items():
                if m and "mse" in m:
                    worst.append((i, w["window_start"], w["window_end"], model_name, m["mse"], m.get("directional_accuracy")))
        worst.sort(key=lambda x: x[4], reverse=True)
        lines.append("**Worst windows by MSE (top 5):**")
        lines.append("")
        for i, (idx, start, end, model, mse, acc) in enumerate(worst[:5]):
            lines.append(f"- Window {idx+1} [{start} .. {end}], model={model}: MSE={mse}, dir_acc={acc}")
        lines.append("")
        lines.append("**Per-window sample counts:**")
        for i, w in enumerate(windows):
            lines.append(f"- Window {i+1} [{w.get('window_start')} .. {w.get('window_end')}]: n={w.get('n_samples', 0)}")
    lines.append("")
    lines.append("*Report generated from stored backtest artifact (deterministic).*")

    report = "\n".join(lines)
    if out_path is not None:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(report, encoding="utf-8")
    return report
