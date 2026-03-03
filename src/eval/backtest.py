"""
Backtest: load test split, run baselines (and optional TF model), compute metrics, write summary.
Also writes a time-aligned predictions CSV (latest_predictions.csv and versioned predictions.csv).
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.eval.baselines import get_baseline_predictions, list_baseline_names
from src.eval.metrics import compute_metrics


def _target_date_from_asof(config: Dict[str, Any], asof_date: str) -> str:
    """Derive target (predicted) date from feature date + forward_return_days."""
    fw = config.get("feature_windows") or {}
    days = int(fw.get("forward_return_days", 1))
    d = pd.to_datetime(asof_date)
    return (d + pd.Timedelta(days=days)).strftime("%Y-%m-%d")


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
) -> Tuple[Optional[Dict[str, float]], Optional[Any]]:
    """If a trained run exists, evaluate with compute_metrics. Returns (metrics, y_pred) for persistence."""
    try:
        from src.train.load import load_trained_model, predict_with_trained_model
    except Exception:
        return None, None
    if not models_path.exists():
        return None, None
    run_id = config.get("eval", {}).get("tensorflow_run_id", "").strip() or None
    if run_id:
        run_dir = models_path / run_id
    else:
        candidates = [d.name for d in models_path.iterdir() if d.is_dir() and d.name.startswith(dataset_version + "_")]
        if not candidates:
            return None, None
        run_dir = models_path / sorted(candidates)[-1]
    has_model = (run_dir / "model.keras").exists() or (run_dir / "saved_model").exists()
    if not has_model or not (run_dir / "run_record.json").exists():
        return None, None
    try:
        model, record = load_trained_model(run_dir)
        y_pred = predict_with_trained_model(model, record, test_df)
        return compute_metrics(y_true, y_pred), y_pred
    except Exception:
        return None, None


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


def _build_predictions_df(
    test_df: pd.DataFrame,
    predictions_by_model: Dict[str, Any],
    config: Dict[str, Any],
    fold_id: int = -1,
) -> pd.DataFrame:
    """Build time-aligned predictions DataFrame from test rows and per-model y_pred arrays."""
    rows: List[Dict[str, Any]] = []
    date_col = "date" if "date" in test_df.columns else test_df.columns[0]
    ticker_col = "ticker" if "ticker" in test_df.columns else None
    target_col = "target_forward_return"
    for model_name, y_pred in predictions_by_model.items():
        if y_pred is None or len(y_pred) != len(test_df):
            continue
        for i in range(len(test_df)):
            row = test_df.iloc[i]
            asof = str(row[date_col])
            rows.append({
                "ticker": row[ticker_col] if ticker_col else "",
                "asof_date": asof,
                "target_date": _target_date_from_asof(config, asof),
                "y_true": float(row[target_col]),
                "y_pred": float(y_pred[i]) if hasattr(y_pred[i], "__float__") else float(y_pred[i]),
                "model_name": model_name,
                "fold_id": fold_id,
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["ticker", "asof_date", "target_date", "y_true", "y_pred", "model_name", "fold_id"])


def _write_predictions_csv(
    reports_path: Path,
    dataset_version: str,
    predictions_df: pd.DataFrame,
    log: Any,
) -> None:
    """Write reports/latest_predictions.csv and reports/<dataset_version>/predictions.csv."""
    if predictions_df.empty:
        log("No predictions to write; skipping predictions CSV")
        return
    reports_path.mkdir(parents=True, exist_ok=True)
    latest_path = reports_path / "latest_predictions.csv"
    predictions_df.to_csv(latest_path, index=False)
    log(f"Wrote {latest_path}")
    out_dir = reports_path / dataset_version
    out_dir.mkdir(parents=True, exist_ok=True)
    versioned_path = out_dir / "predictions.csv"
    predictions_df.to_csv(versioned_path, index=False)
    log(f"Wrote {versioned_path}")


def _write_latest_outputs(
    reports_path: Path,
    summary: Optional[Dict[str, Any]],
    artifact_path: Optional[Path],
    log: Any,
) -> None:
    """
    Write reports/latest_metrics.json and reports/latest_backtest.md (overwritten each run).
    Use summary for single-window; use artifact_path (backtest_run.json) for walk-forward.
    """
    from src.eval.report import generate_report, generate_single_window_report

    reports_path.mkdir(parents=True, exist_ok=True)
    latest_json = reports_path / "latest_metrics.json"
    latest_md = reports_path / "latest_backtest.md"

    if summary is not None:
        with open(latest_json, "w") as f:
            json.dump(summary, f, indent=2)
        latest_md.write_text(generate_single_window_report(summary), encoding="utf-8")
    else:
        with open(artifact_path) as f:
            data = json.load(f)
        setup = data.get("setup", {})
        agg = data.get("aggregated_metrics", {})
        latest_summary = {
            "dataset_version": setup.get("dataset_version"),
            "train_end": setup.get("train_end"),
            "val_start": setup.get("val_start"),
            "val_end": setup.get("val_end"),
            "test_start": setup.get("test_start"),
            "n_test": None,
            "models": agg,
            "folds": data.get("folds", []),
            "aggregate": data.get("aggregate", {}),
        }
        with open(latest_json, "w") as f:
            json.dump(latest_summary, f, indent=2)
        generate_report(artifact_path, out_path=latest_md)
    log(f"Wrote {latest_json} and {latest_md}")


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

    eval_cfg = config.get("eval") or {}
    wf = eval_cfg.get("walk_forward") or {}
    fold_size = eval_cfg.get("fold_size_days") or wf.get("window_days")
    step_size = eval_cfg.get("step_size_days") or wf.get("step_days")
    if fold_size and step_size:
        # Walk-forward: iterate folds, save artifact, generate report
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
        _write_latest_outputs(reports_path, None, artifact_path, log)
        predictions_list = artifact.get("predictions") or []
        if predictions_list:
            predictions_df = pd.DataFrame(predictions_list)
            _write_predictions_csv(reports_path, dataset_version, predictions_df, log)

        # Attach a compact backtest_summary to the trained run's run_record.json (if a run exists)
        try:
            num_folds = len(artifact.get("folds") or [])
            aggregate = artifact.get("aggregate") or {}
            # Path to artifact relative to repo root for portability
            rel_artifact_path = artifact_path.relative_to(repo_root).as_posix()
            backtest_summary = {
                "num_folds": num_folds,
                "aggregate": aggregate,
                "artifact_path": rel_artifact_path,
            }

            run_id = (config.get("eval") or {}).get("tensorflow_run_id", "").strip() or None
            if not run_id and models_path.exists():
                candidates = [
                    d.name
                    for d in models_path.iterdir()
                    if d.is_dir() and d.name.startswith(dataset_version + "_")
                ]
                run_id = sorted(candidates)[-1] if candidates else None
            if run_id:
                run_dir = models_path / run_id
                rr_path = run_dir / "run_record.json"
                if rr_path.exists():
                    with open(rr_path) as f:
                        rr = json.load(f)
                    rr["backtest_summary"] = backtest_summary
                    with open(rr_path, "w") as f:
                        json.dump(rr, f, indent=2)
                    log(f"Attached backtest_summary to {rr_path}")
        except Exception:
            # Backtest artifacts are still written even if attaching summary fails
            log("Warning: could not attach backtest_summary to run_record.json")

        return artifact
    else:
        # Single-window (legacy)
        th = config.get("time_horizon", {})
        y_true = test_df["target_forward_return"].astype(float).values
        summary = {
            "dataset_version": dataset_version,
            "train_end": th.get("train_end"),
            "val_start": th.get("val_start"),
            "val_end": th.get("val_end"),
            "test_start": th.get("test_start"),
            "n_test": len(test_df),
            "models": {},
        }
        predictions_by_model: Dict[str, Any] = {}
        for name in list_baseline_names():
            log(f"Evaluating baseline: {name}")
            y_pred = get_baseline_predictions(name, train_df, test_df)
            summary["models"][name] = compute_metrics(y_true, y_pred)
            predictions_by_model[name] = y_pred
        tf_metrics, tf_y_pred = _evaluate_tensorflow_if_available(
            config, processed_path, models_path, dataset_version, train_df, test_df, y_true, log
        )
        summary["models"]["tensorflow"] = tf_metrics
        if tf_y_pred is not None:
            predictions_by_model["tensorflow"] = tf_y_pred
        reports_path.mkdir(parents=True, exist_ok=True)
        out_dir = reports_path / dataset_version
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "metrics_summary.json"
        with open(out_file, "w") as f:
            json.dump(summary, f, indent=2)
        log(f"Wrote {out_file}")
        from src.eval.report import generate_single_window_report
        versioned_md = out_dir / "backtest_report.md"
        versioned_md.write_text(generate_single_window_report(summary), encoding="utf-8")
        log(f"Wrote {versioned_md}")
        _write_latest_outputs(reports_path, summary, None, log)
        predictions_df = _build_predictions_df(test_df, predictions_by_model, config, fold_id=-1)
        _write_predictions_csv(reports_path, dataset_version, predictions_df, log)
        return summary
