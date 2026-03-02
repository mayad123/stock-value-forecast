"""
Training routine: load processed data, train on train partition, evaluate on validation,
produce SavedModel artifact and run record (config hash, git commit, seeds, schema, metrics).
Every run dir contains run_record.json, model artifact, and metrics_summary.json for audit.
"""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import tensorflow as tf

from src._cli import config_hash_from_dict, config_hash_from_file, get_git_commit
from src.eval.metrics import compute_metrics
from src.features.price_features import FEATURE_NAMES
from src.train.data import load_feature_manifest, load_train_val, resolve_processed_version, get_X_y
from src.train.model import build_model


def _run_id(dataset_version: str) -> str:
    """Stable run id for this training run."""
    return f"{dataset_version}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}"


def run_training(
    config: Dict[str, Any],
    processed_root: Optional[Path] = None,
    models_root: Optional[Path] = None,
    dataset_version_hint: str = "latest",
    log: Optional[Any] = None,
) -> str:
    """
    Load processed train/val, train TF model, save SavedModel and run record.
    Returns run_id (directory name under models/).
    """
    if log is None:
        def log(msg: str) -> None:
            print(f"[TRAIN] {msg}")

    paths_cfg = config.get("paths", {})
    repo_root = Path(__file__).resolve().parents[2]
    processed_path = processed_root or (repo_root / paths_cfg.get("data_processed", "data/processed"))
    if not processed_path.is_absolute():
        processed_path = repo_root / processed_path
    models_path = models_root or (repo_root / paths_cfg.get("models", "models"))
    if not models_path.is_absolute():
        models_path = repo_root / models_path

    # Self-describing artifact: config hash (exact YAML when path available) and git commit
    config_path_str = config.get("_config_path")
    if config_path_str and Path(config_path_str).exists():
        try:
            config_hash = config_hash_from_file(Path(config_path_str))
        except Exception:
            config_hash = config_hash_from_dict(config)
    else:
        config_hash = config_hash_from_dict(config)
    git_commit_hash = get_git_commit(repo_root)

    dataset_version = resolve_processed_version(processed_path, dataset_version_hint)
    log(f"Processed dataset version: {dataset_version}")

    train_df, val_df = load_train_val(processed_path, dataset_version)
    log(f"Train rows: {len(train_df)}, val rows: {len(val_df)}")

    if len(train_df) == 0:
        raise ValueError("No training data; need at least one train row")

    feature_manifest = load_feature_manifest(processed_path, dataset_version)
    manifest_cols = feature_manifest.get("feature_columns")
    if manifest_cols:
        feature_cols = [c for c in manifest_cols if c in train_df.columns]
    else:
        feature_cols = [c for c in FEATURE_NAMES if c in train_df.columns]
    if len(feature_cols) == 0:
        raise ValueError("No feature columns found in train data")
    log(f"Using {len(feature_cols)} features: {feature_cols}")
    n_features = len(feature_cols)

    X_train, y_train = get_X_y(train_df, feature_cols)
    X_val, y_val = get_X_y(val_df, feature_cols)

    # Normalize: fit on train only, apply to train and val
    mean = np.mean(X_train, axis=0, dtype=np.float32)
    std = np.std(X_train, axis=0, dtype=np.float32)
    std[std == 0] = 1.0
    X_train_n = (X_train - mean) / std
    has_val = len(val_df) > 0
    if has_val:
        X_val_n = (X_val - mean) / std
    else:
        X_val_n = None
        y_val = np.array([], dtype=np.float32)

    hp = config.get("training", {})
    epochs = int(hp.get("epochs", 50))
    batch_size = int(hp.get("batch_size", 32))
    learning_rate = float(hp.get("learning_rate", 0.001))
    patience = int(hp.get("early_stopping_patience", 10))
    seed = int(hp.get("seed", 42))
    np.random.seed(seed)
    tf.random.set_seed(seed)
    random.seed(seed)
    random_seeds = {"numpy": seed, "tensorflow": seed, "python": seed}

    model = build_model(
        n_features=n_features,
        units=16,
        dropout_rate=0.3,
        learning_rate=learning_rate,
    )

    callbacks = []
    if patience > 0 and has_val:
        callbacks.append(
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss",
                patience=patience,
                restore_best_weights=True,
            )
        )

    if has_val:
        history = model.fit(
            X_train_n, y_train,
            validation_data=(X_val_n, y_val),
            epochs=epochs,
            batch_size=batch_size,
            callbacks=callbacks,
            verbose=1,
        )
        train_metrics = {
            "loss": float(history.history["loss"][-1]),
            "mae": float(history.history["mae"][-1]),
        }
        val_metrics_keras = {
            "val_loss": float(history.history["val_loss"][-1]),
            "val_mae": float(history.history["val_mae"][-1]),
        }
        y_val_pred = model.predict(X_val_n, verbose=0).flatten()
        val_metrics_shared = compute_metrics(y_val, y_val_pred)
    else:
        history = model.fit(
            X_train_n, y_train,
            epochs=epochs,
            batch_size=batch_size,
            verbose=1,
        )
        train_metrics = {
            "loss": float(history.history["loss"][-1]),
            "mae": float(history.history["mae"][-1]),
        }
        val_metrics_keras = {}
        val_metrics_shared = {}

    run_id = _run_id(dataset_version)
    out_dir = models_path / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save model (Keras 3: .keras file; no save_format=tf)
    saved_model_path = out_dir / "model.keras"
    model.save(saved_model_path)
    log(f"Saved model: {saved_model_path}")

    # Run record: config hash, git commit, seeds, schema, dataset refs, metrics, scaler
    feature_manifest = load_feature_manifest(processed_path, dataset_version)
    split_boundaries = feature_manifest.get("split_boundaries") or config.get("time_horizon", {})
    model_input_shape: List[Optional[int]] = [int(s) if s is not None else None for s in model.input_shape]
    run_record = {
        "run_id": run_id,
        "config_hash": config_hash,
        "config_path": config_path_str,
        "git_commit_hash": git_commit_hash,
        "random_seeds": random_seeds,
        "model_input_shape": model_input_shape,
        "config": {
            "training": hp,
            "time_horizon": config.get("time_horizon", {}),
            "feature_windows": config.get("feature_windows", {}),
            "paths": paths_cfg,
        },
        "dataset_version": dataset_version,
        "feature_manifest_path": str(processed_path / dataset_version / "feature_manifest.json"),
        "split_boundaries": split_boundaries,
        "feature_columns": feature_cols,
        "scaler": {
            "mean": mean.tolist(),
            "scale": std.tolist(),
        },
        "train_metrics": train_metrics,
        "val_metrics_keras": val_metrics_keras,
        "val_metrics": val_metrics_shared,
        "model_path": str(saved_model_path),
    }

    record_path = out_dir / "run_record.json"
    with open(record_path, "w") as f:
        json.dump(run_record, f, indent=2)
    log(f"Run record: {record_path}")

    # Metrics summary in run dir so reviewer can open one folder and see what was achieved
    metrics_summary = {
        "run_id": run_id,
        "config_hash": config_hash,
        "git_commit_hash": git_commit_hash,
        "dataset_version": dataset_version,
        "feature_columns": feature_cols,
        "model_input_shape": model_input_shape,
        "split_boundaries": split_boundaries,
        "train_metrics": train_metrics,
        "val_metrics_keras": val_metrics_keras,
        "val_metrics": val_metrics_shared,
    }
    metrics_path = out_dir / "metrics_summary.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics_summary, f, indent=2)
    log(f"Metrics summary: {metrics_path}")

    return run_id
