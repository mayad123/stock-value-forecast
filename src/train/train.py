"""
Training routine: load processed data, train on train partition, evaluate on validation,
produce SavedModel artifact and run record (config hash, git commit, seeds, schema, metrics).
Trains one model across all tickers with explicit ticker identity (one-hot) so the model
does not collapse to average ticker behavior. Ticker encoding mapping is persisted for serve.
"""

import hashlib
import json
import os
import random
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import tensorflow as tf

# Avoid GPU init / thread contention that can block before first epoch (mutex.cc Lock blocking)
try:
    tf.config.set_visible_devices([], "GPU")
except Exception:
    pass
try:
    tf.config.threading.set_intra_op_parallelism_threads(1)
    tf.config.threading.set_inter_op_parallelism_threads(1)
except Exception:
    pass
# Force one-time TF runtime init here so any internal lock happens at import, not during fit()
try:
    _ = tf.constant(0)
except Exception:
    pass

from src._cli import config_hash_from_dict, config_hash_from_file, get_git_commit
from src.core.artifacts import deploy_artifacts_models_path, run_id_from_version
from src.core.paths import get_paths, repo_root
from src.eval.baselines import get_baseline_predictions, list_baseline_names
from src.eval.metrics import compute_metrics
from src.features.price_features import FEATURE_NAMES, TARGET_NAME
from src.data.versioning import resolve_processed_version
from src.train.data import load_feature_manifest, load_train_val, get_X_y
from src.train.model import build_model

TICKER_COL = "ticker"


def _ticker_encoding_fingerprint(ticker_to_idx: Dict[str, int]) -> str:
    """Stable fingerprint of the ticker encoding mapping for run record traceability."""
    blob = json.dumps(ticker_to_idx, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _add_ticker_onehot(
    df: pd.DataFrame,
    ticker_to_idx: Dict[str, int],
    ticker_columns: List[str],
) -> None:
    """Add one-hot ticker columns to df in place. Unseen tickers get all zeros."""
    for col in ticker_columns:
        df[col] = 0.0
    for ticker, idx in ticker_to_idx.items():
        if idx < len(ticker_columns):
            col = ticker_columns[idx]
            df.loc[df[TICKER_COL].astype(str) == ticker, col] = 1.0


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
        from src.logging_config import get_logger
        _log = get_logger("train")
        def log(msg: str) -> None:
            _log.info("%s", msg)

    paths = get_paths(config)
    root = repo_root()
    processed_path = processed_root or paths["processed_path"]
    models_path = models_root or paths["models_path"]

    # Self-describing artifact: config hash (exact YAML when path available) and git commit
    config_path_str = config.get("_config_path")
    if config_path_str and Path(config_path_str).exists():
        try:
            config_hash = config_hash_from_file(Path(config_path_str))
        except Exception:
            config_hash = config_hash_from_dict(config)
    else:
        config_hash = config_hash_from_dict(config)
    git_commit_hash = get_git_commit(root)

    dataset_version = resolve_processed_version(processed_path, dataset_version_hint)
    log(f"Processed dataset version: {dataset_version}")

    train_df, val_df = load_train_val(processed_path, dataset_version)
    log(f"Train rows: {len(train_df)}, val rows: {len(val_df)}")

    if len(train_df) == 0:
        raise ValueError("No training data; need at least one train row")

    # Ticker identity: one-hot encoding so model sees which ticker (no collapse to average)
    if TICKER_COL not in train_df.columns:
        raise ValueError("Training data must include a 'ticker' column for multi-ticker training.")
    tickers = sorted(train_df[TICKER_COL].astype(str).unique().tolist())
    ticker_to_idx = {t: i for i, t in enumerate(tickers)}
    ticker_columns = [f"ticker_{i}" for i in range(len(tickers))]
    _add_ticker_onehot(train_df, ticker_to_idx, ticker_columns)
    _add_ticker_onehot(val_df, ticker_to_idx, ticker_columns)
    log(f"Tickers in training: {tickers} (one-hot encoded)")

    feature_manifest = load_feature_manifest(processed_path, dataset_version)
    manifest_cols = feature_manifest.get("feature_columns")
    price_cols = [c for c in (manifest_cols or FEATURE_NAMES) if c in train_df.columns and c not in ticker_columns]
    if len(price_cols) == 0:
        raise ValueError("No price feature columns found in train data")
    feature_cols = ticker_columns + price_cols
    log(f"Using {len(feature_cols)} features: {len(ticker_columns)} ticker + {len(price_cols)} price")

    X_train, y_train = get_X_y(train_df, feature_cols)
    X_val, y_val = get_X_y(val_df, feature_cols)

    # Normalize: fit on train only; do not scale one-hot (ticker) columns
    mean = np.mean(X_train, axis=0, dtype=np.float32)
    std = np.std(X_train, axis=0, dtype=np.float32)
    std[std == 0] = 1.0
    n_ticker = len(ticker_columns)
    mean[:n_ticker] = 0.0
    std[:n_ticker] = 1.0
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

    log("Building model...")
    model = build_model(
        n_features=len(feature_cols),
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

    log(f"Starting fit (epochs={epochs}, batch_size={batch_size})...")
    baseline_metrics: Dict[str, Dict[str, Any]] = {}
    baseline_deltas: Dict[str, Dict[str, float]] = {}

    if has_val:
        history = model.fit(
            X_train_n, y_train,
            validation_data=(X_val_n, y_val),
            epochs=epochs,
            batch_size=batch_size,
            callbacks=callbacks,
            verbose=1,
        )
        epochs_ran = int(len(history.history.get("loss", [])) or 0)
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

        # Baselines on the exact same validation slice as val_metrics
        for name in list_baseline_names():
            y_val_pred_baseline = get_baseline_predictions(name, train_df, val_df)
            m = compute_metrics(y_val, y_val_pred_baseline)
            baseline_metrics[name] = m

        # Baseline deltas: model_metric - baseline_metric (MAE, RMSE)
        if baseline_metrics and "mae" in val_metrics_shared and "rmse" in val_metrics_shared:
            for name, m in baseline_metrics.items():
                deltas: Dict[str, float] = {}
                if "mae" in m:
                    deltas["mae"] = float(val_metrics_shared["mae"]) - float(m["mae"])
                if "rmse" in m:
                    deltas["rmse"] = float(val_metrics_shared["rmse"]) - float(m["rmse"])
                baseline_deltas[name] = deltas
    else:
        history = model.fit(
            X_train_n, y_train,
            epochs=epochs,
            batch_size=batch_size,
            verbose=1,
        )
        epochs_ran = int(len(history.history.get("loss", [])) or 0)
        train_metrics = {
            "loss": float(history.history["loss"][-1]),
            "mae": float(history.history["mae"][-1]),
        }
        val_metrics_keras = {}
        val_metrics_shared = {}

    run_id = run_id_from_version(dataset_version)
    out_dir = models_path / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save model (Keras 3: .keras file; no save_format=tf)
    saved_model_path = out_dir / "model.keras"
    model.save(saved_model_path)
    log(f"Saved model: {saved_model_path}")

    # Run record: config hash, git commit, seeds, schema, dataset refs, metrics, scaler, ticker encoding
    feature_manifest = load_feature_manifest(processed_path, dataset_version)
    split_boundaries = feature_manifest.get("split_boundaries") or config.get("time_horizon", {})
    model_input_shape: List[Optional[int]] = [int(s) if s is not None else None for s in model.input_shape]

    # Paths in run_record should be relative to repo root for portability
    def _rel(path_str: Optional[str]) -> Optional[str]:
        if not path_str:
            return None
        try:
            return os.path.relpath(path_str, root)
        except Exception:
            return path_str

    rel_config_path = _rel(config_path_str) if config_path_str else None
    rel_feature_manifest_path = _rel(str(processed_path / dataset_version / "feature_manifest.json"))
    rel_model_path = _rel(str(saved_model_path))

    # Data provenance: coverage and counts for the processed dataset used for training
    features_path = processed_path / dataset_version / "features.csv"
    data_provenance: Dict[str, Any] = {}
    try:
        df_all = pd.read_csv(features_path)
        if "split" in df_all.columns and "ticker" in df_all.columns and "date" in df_all.columns:
            split_counts = df_all["split"].value_counts().to_dict()
            n_train_samples = int(split_counts.get("train", 0))
            n_val_samples = int(split_counts.get("val", 0))
            n_test_samples = int(split_counts.get("test", 0))

            rows_per_ticker: Dict[str, Dict[str, int]] = {}
            date_range_per_ticker: Dict[str, Dict[str, Optional[str]]] = {}
            for ticker, g in df_all.groupby("ticker", sort=True):
                sc = g["split"].value_counts().to_dict()
                rows_per_ticker[str(ticker)] = {
                    "train": int(sc.get("train", 0)),
                    "val": int(sc.get("val", 0)),
                    "test": int(sc.get("test", 0)),
                }
                dates = pd.to_datetime(g["date"])
                if not dates.empty:
                    date_range_per_ticker[str(ticker)] = {
                        "min": dates.min().strftime("%Y-%m-%d"),
                        "max": dates.max().strftime("%Y-%m-%d"),
                    }
                else:
                    date_range_per_ticker[str(ticker)] = {"min": None, "max": None}

            data_provenance = {
                "n_train_samples": n_train_samples,
                "n_val_samples": n_val_samples,
                "n_test_samples": n_test_samples,
                "rows_per_ticker": rows_per_ticker,
                "date_range_per_ticker": date_range_per_ticker,
                "rows_dropped_feature_windows": int(
                    feature_manifest.get("rows_dropped_feature_windows", 0)
                ),
            }
    except Exception:
        data_provenance = {}

    # Effective training configuration vs. what actually ran (epochs and early stopping)
    epochs_ran_int = int(epochs_ran) if "epochs_ran" in locals() else 0
    early_stopping_triggered = bool(
        patience > 0 and has_val and epochs_ran_int < epochs
    )
    training_effective = {
        "epochs_configured": int(epochs),
        "epochs_ran": epochs_ran_int,
        "early_stopping_triggered": early_stopping_triggered,
    }

    # Target metadata: what the model predicts
    fw_cfg = config.get("feature_windows") or feature_manifest.get("feature_windows") or {}
    horizon_days = int(fw_cfg.get("forward_return_days", 1))
    target = {
        "target_name": TARGET_NAME,
        "horizon_days": horizon_days,
        "return_type": "simple",          # adj.shift(-h)/adj - 1.0
        "scaling": None,                  # no additional scaling applied
    }
    tensorflow_version = tf.__version__
    run_record = {
        "run_id": run_id,
        "config_hash": config_hash,
        "config_path": rel_config_path,
        "git_commit_hash": git_commit_hash,
        "tensorflow_version": tensorflow_version,
        "random_seeds": random_seeds,
        "model_input_shape": model_input_shape,
        "config": {
            "training": hp,
            "time_horizon": config.get("time_horizon", {}),
            "feature_windows": config.get("feature_windows", {}),
            "paths": config.get("paths", {}),
        },
        "target": target,
        "dataset_version": dataset_version,
        "feature_manifest_path": rel_feature_manifest_path,
        "split_boundaries": split_boundaries,
        "feature_columns": feature_cols,
        "tickers": tickers,
        "ticker_encoding": "one-hot",
        "ticker_to_idx": ticker_to_idx,
        "ticker_columns": ticker_columns,
        "ticker_encoding_fingerprint": _ticker_encoding_fingerprint(ticker_to_idx),
        "scaler": {
            "mean": mean.tolist(),
            "scale": std.tolist(),
        },
        "data_provenance": data_provenance,
        "training_effective": training_effective,
        "train_metrics": train_metrics,
        "val_metrics_keras": val_metrics_keras,
        "val_metrics": val_metrics_shared,
        "baseline_metrics": baseline_metrics,
        "baseline_deltas": baseline_deltas,
        "model_path": rel_model_path,
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
        "tickers": tickers,
        "ticker_encoding": "one-hot",
        "ticker_encoding_fingerprint": run_record["ticker_encoding_fingerprint"],
        "feature_columns": feature_cols,
        "model_input_shape": model_input_shape,
        "split_boundaries": split_boundaries,
        "train_metrics": train_metrics,
        "val_metrics_keras": val_metrics_keras,
        "val_metrics": val_metrics_shared,
        "baseline_metrics": baseline_metrics,
        "baseline_deltas": baseline_deltas,
        "target": target,
        "training_effective": training_effective,
    }
    metrics_path = out_dir / "metrics_summary.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics_summary, f, indent=2)
    log(f"Metrics summary: {metrics_path}")

    # Mirror this run to deploy_artifacts so the frontend/serve use it when models/ is absent (e.g. cloud)
    if os.environ.get("UPDATE_DEPLOY_ARTIFACTS", "1") == "1":
        deploy_models = deploy_artifacts_models_path(root)
        deploy_models.mkdir(parents=True, exist_ok=True)
        dest = deploy_models / run_id
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(out_dir, dest)
        log(f"Deploy artifact updated: {dest} (frontend will use this when models/ is empty)")

    return run_id
