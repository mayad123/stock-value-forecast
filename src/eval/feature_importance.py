"""
Permutation-based feature importance for the trained model.

Uses the validation (or test) set: for each feature, permutes its values and measures
the increase in MSE. Higher increase = more important feature. Writes JSON and PNG to reports/.
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd


def _load_splits(processed_path: Path, dataset_version: str) -> tuple:
    """Load features.csv and return (train_df, val_df, test_df). Val may be empty."""
    path = processed_path / dataset_version / "features.csv"
    if not path.exists():
        raise FileNotFoundError(f"Features not found: {path}")
    df = pd.read_csv(path)
    if "split" not in df.columns:
        raise ValueError("Features CSV must have 'split' column (train/val/test)")
    train_df = df[df["split"] == "train"].copy()
    val_df = df[df["split"] == "val"].copy()
    test_df = df[df["split"] == "test"].copy()
    return train_df, val_df, test_df


def _permutation_importance(
    model: Any,
    run_record: Dict[str, Any],
    eval_df: pd.DataFrame,
    feature_columns: List[str],
    n_repeats: int = 5,
    random_state: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Compute permutation importance: for each feature, shuffle and measure MSE increase.
    Returns list of {"feature": name, "importance": mean_increase, "std": std} sorted by importance desc.
    """
    from src.train.load import predict_with_trained_model

    rng = np.random.default_rng(random_state)
    y_true = eval_df["target_forward_return"].astype(np.float32).values
    y_pred_baseline = predict_with_trained_model(model, run_record, eval_df)
    baseline_mse = float(np.mean((y_true - y_pred_baseline) ** 2))

    results: List[Dict[str, Any]] = []
    for col in feature_columns:
        if col not in eval_df.columns:
            continue
        increases: List[float] = []
        for _ in range(n_repeats):
            eval_perm = eval_df.copy()
            eval_perm[col] = eval_perm[col].sample(frac=1, random_state=rng).values
            y_pred_perm = predict_with_trained_model(model, run_record, eval_perm)
            perm_mse = float(np.mean((y_true - y_pred_perm) ** 2))
            increases.append(perm_mse - baseline_mse)
        results.append({
            "feature": col,
            "importance": float(np.mean(increases)),
            "std": float(np.std(increases)) if len(increases) > 1 else 0.0,
        })
    results.sort(key=lambda x: -x["importance"])
    return results


def run_feature_importance(
    config: Dict[str, Any],
    processed_root: Optional[Path] = None,
    dataset_version_hint: str = "latest",
    n_repeats: int = 5,
    log: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Compute permutation feature importance for the trained model, write JSON and PNG to reports/.
    Uses validation set if available, else test set. Returns the artifact dict.
    """
    if log is None:
        from src.logging_config import get_logger
        _log = get_logger("feature_importance")
        def log(msg: str) -> None:
            _log.info("%s", msg)

    if dataset_version_hint == "latest":
        dataset_version_hint = config.get("eval", {}).get("processed_version", "latest")

    from src.core.artifacts import resolve_run_dir
    from src.core.paths import get_paths
    from src.data.versioning import resolve_processed_version

    paths = get_paths(config)
    processed_path = processed_root or paths["processed_path"]
    reports_path = paths["reports_path"]
    models_path = paths["models_path"]

    dataset_version = resolve_processed_version(processed_path, dataset_version_hint)
    log(f"Dataset version: {dataset_version}")

    train_df, val_df, test_df = _load_splits(processed_path, dataset_version)
    eval_df = val_df if len(val_df) > 0 else test_df
    if len(eval_df) == 0:
        log("No validation or test rows; skipping feature importance")
        return {"dataset_version": dataset_version, "feature_importance": []}

    log(f"Using {len(eval_df)} rows for permutation importance")

    run_id_hint = (config.get("eval") or {}).get("tensorflow_run_id", "").strip() or None
    run_dir = resolve_run_dir(models_path, dataset_version, run_id_hint=run_id_hint)
    log(f"Model run: {run_dir.name}")

    from src.train.load import load_trained_model
    model, run_record = load_trained_model(run_dir)
    feature_columns = list(run_record.get("feature_columns", []))
    if not feature_columns:
        log("No feature_columns in run_record; skipping")
        return {"dataset_version": dataset_version, "feature_importance": []}

    importance_list = _permutation_importance(
        model, run_record, eval_df, feature_columns,
        n_repeats=n_repeats, random_state=42,
    )

    artifact = {
        "dataset_version": dataset_version,
        "model_run_id": run_dir.name,
        "n_eval_samples": len(eval_df),
        "metric": "mse_increase",
        "n_repeats": n_repeats,
        "feature_importance": importance_list,
    }

    reports_path.mkdir(parents=True, exist_ok=True)
    out_dir = reports_path / dataset_version
    out_dir.mkdir(parents=True, exist_ok=True)

    latest_json = reports_path / "latest_feature_importance.json"
    with open(latest_json, "w") as f:
        json.dump(artifact, f, indent=2)
    log(f"Wrote {latest_json}")

    versioned_json = out_dir / "feature_importance.json"
    with open(versioned_json, "w") as f:
        json.dump(artifact, f, indent=2)
    log(f"Wrote {versioned_json}")

    # PNG bar chart
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        names = [x["feature"] for x in importance_list]
        values = [x["importance"] for x in importance_list]
        stds = [x["std"] for x in importance_list]
        fig, ax = plt.subplots(figsize=(8, max(4, len(names) * 0.35)))
        y_pos = np.arange(len(names))
        ax.barh(y_pos, values, xerr=stds if any(s > 0 for s in stds) else None, capsize=2)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names, fontsize=10)
        ax.set_xlabel("Permutation importance (MSE increase)")
        ax.set_title("Feature importance (permutation)")
        fig.tight_layout()
        latest_png = reports_path / "latest_feature_importance.png"
        fig.savefig(latest_png, dpi=100, bbox_inches="tight")
        log(f"Wrote {latest_png}")
        versioned_png = out_dir / "feature_importance.png"
        fig.savefig(versioned_png, dpi=100, bbox_inches="tight")
        log(f"Wrote {versioned_png}")
        plt.close(fig)
    except ImportError:
        log("matplotlib not installed; skipping PNG")

    return artifact
