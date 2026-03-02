"""
Backtest: load test split, run baselines (and optional TF model), compute metrics, write summary.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from src.eval.baselines import get_baseline_predictions, list_baseline_names
from src.eval.metrics import compute_metrics


def resolve_processed_version(processed_root: Path, version_hint: str = "latest") -> str:
    """Resolve processed dataset version. 'latest' -> lexicographically last dir with features.csv."""
    if not processed_root.exists():
        raise FileNotFoundError(f"Processed root not found: {processed_root}")

    if version_hint != "latest":
        features_path = processed_root / version_hint / "features.csv"
        if features_path.exists():
            return version_hint
        raise FileNotFoundError(f"Processed version not found: {version_hint}")

    subdirs = [d.name for d in processed_root.iterdir() if d.is_dir() and (d / "features.csv").exists()]
    if not subdirs:
        raise FileNotFoundError(f"No processed datasets with features.csv in {processed_root}")
    return sorted(subdirs)[-1]


def _evaluate_tensorflow_if_available(
    config: Dict[str, Any],
    processed_path: Path,
    models_path: Path,
    dataset_version: str,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    y_true: Any,
    log: Any,
) -> Optional[Dict[str, float]]:
    """If a trained run exists for this dataset (or run_id in config), evaluate with compute_metrics."""
    try:
        from src.train.load import load_trained_model, predict_with_trained_model
    except Exception:
        return None
    if not models_path.exists():
        return None
    run_id = config.get("eval", {}).get("tensorflow_run_id", "").strip() or None
    if run_id:
        run_dir = models_path / run_id
    else:
        # Prefer latest run whose name starts with dataset_version
        candidates = [d.name for d in models_path.iterdir() if d.is_dir() and d.name.startswith(dataset_version + "_")]
        if not candidates:
            return None
        run_dir = models_path / sorted(candidates)[-1]
    has_model = (run_dir / "model.keras").exists() or (run_dir / "saved_model").exists()
    if not has_model or not (run_dir / "run_record.json").exists():
        return None
    try:
        model, record = load_trained_model(run_dir)
        y_pred = predict_with_trained_model(model, record, test_df)
        return compute_metrics(y_true, y_pred)
    except Exception:
        return None


def load_processed_splits(
    processed_root: Path,
    dataset_version: str,
) -> tuple:
    """Load features.csv and return (train_df, test_df)."""
    path = processed_root / dataset_version / "features.csv"
    if not path.exists():
        raise FileNotFoundError(f"Features not found: {path}")
    df = pd.read_csv(path)
    if "split" not in df.columns:
        raise ValueError("Features CSV must have 'split' column (train/val/test)")
    train_df = df[df["split"] == "train"].copy()
    test_df = df[df["split"] == "test"].copy()
    return train_df, test_df


def _load_feature_manifest(processed_path: Path, dataset_version: str) -> Dict[str, Any]:
    """Load feature_manifest.json for run record."""
    path = processed_path / dataset_version / "feature_manifest.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def run_backtest(
    config: Dict[str, Any],
    processed_root: Optional[Path] = None,
    dataset_version_hint: str = "latest",
    log: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Evaluate baselines and TF model. If eval.walk_forward is set, run walk-forward
    backtest and generate a human-readable report; else single-window summary.
    Returns the summary/artifact dict and writes to reports/.
    """
    if log is None:
        def log(msg: str) -> None:
            print(f"[BACKTEST] {msg}")

    paths_cfg = config.get("paths", {})
    repo_root = Path(__file__).resolve().parents[2]
    processed_path = processed_root or (repo_root / paths_cfg.get("data_processed", "data/processed"))
    if not processed_path.is_absolute():
        processed_path = repo_root / processed_path
    reports_path = repo_root / paths_cfg.get("reports", "reports")
    if not reports_path.is_absolute():
        reports_path = repo_root / reports_path
    models_path = repo_root / paths_cfg.get("models", "models")
    if not models_path.is_absolute():
        models_path = repo_root / models_path

    dataset_version = resolve_processed_version(processed_path, dataset_version_hint)
    log(f"Processed dataset version: {dataset_version}")

    train_df, test_df = load_processed_splits(processed_path, dataset_version)
    log(f"Train rows: {len(train_df)}, test rows: {len(test_df)}")

    if len(test_df) == 0:
        log("No test rows; skipping backtest")
        return {"dataset_version": dataset_version, "models": {}}

    wf = config.get("eval", {}).get("walk_forward", {})
    if wf.get("window_days") and wf.get("step_days"):
        # Walk-forward: iterate windows, save artifact, generate report
        from src.eval.walk_forward import run_walk_forward
        from src.eval.report import generate_report
        feature_manifest = _load_feature_manifest(processed_path, dataset_version)
        artifact = run_walk_forward(
            config, train_df, test_df, processed_path, models_path,
            dataset_version, feature_manifest, log,
        )
        reports_path.mkdir(parents=True, exist_ok=True)
        out_dir = reports_path / dataset_version
        out_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = out_dir / "backtest_run.json"
        with open(artifact_path, "w") as f:
            json.dump(artifact, f, indent=2)
        log(f"Wrote {artifact_path}")
        report_path = out_dir / "backtest_report.md"
        generate_report(artifact_path, out_path=report_path)
        log(f"Wrote {report_path}")
        return artifact
    else:
        # Single-window (legacy)
        y_true = test_df["target_forward_return"].astype(float).values
        summary = {
            "dataset_version": dataset_version,
            "test_start": config.get("time_horizon", {}).get("test_start"),
            "n_test": len(test_df),
            "models": {},
        }
        for name in list_baseline_names():
            log(f"Evaluating baseline: {name}")
            y_pred = get_baseline_predictions(name, train_df, test_df)
            summary["models"][name] = compute_metrics(y_true, y_pred)
        summary["models"]["tensorflow"] = _evaluate_tensorflow_if_available(
            config, processed_path, models_path, dataset_version, train_df, test_df, y_true, log
        )
        reports_path.mkdir(parents=True, exist_ok=True)
        out_dir = reports_path / dataset_version
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "metrics_summary.json"
        with open(out_file, "w") as f:
            json.dump(summary, f, indent=2)
        log(f"Wrote {out_file}")
        return summary
