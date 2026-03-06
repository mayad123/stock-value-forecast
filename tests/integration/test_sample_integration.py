"""
Integration test on data/sample/: build-features, train, load artifact, one inference.
Proves the trained artifact is loadable and inference returns expected type and shape.
Runs quickly on the checked-in sample dataset.
"""

import importlib.util
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from tests.conftest import REPO_ROOT

DATA_SAMPLE = REPO_ROOT / "data" / "sample"
TENSORFLOW_AVAILABLE = importlib.util.find_spec("tensorflow") is not None


@pytest.mark.skipif(
    not DATA_SAMPLE.exists(),
    reason="data/sample/ not found (run from repo root)",
)
@pytest.mark.skipif(
    not TENSORFLOW_AVAILABLE,
    reason="tensorflow not installed",
)
def test_sample_build_train_load_inference():
    """
    On data/sample/: build features, train, save artifact, load artifact, run one inference.
    Asserts inference output has expected type and shape.
    """
    from src._cli import load_config
    from src.features.price_features import run_build_features
    from src.train.load import load_trained_model, predict_with_trained_model
    from src.train.train import run_training

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        processed_root = tmp / "processed"
        models_root = tmp / "models"
        processed_root.mkdir()
        models_root.mkdir()

        config = load_config(str(REPO_ROOT / "configs" / "recruiter_demo_real.yaml"))
        config["paths"] = {
            "data_raw": str(DATA_SAMPLE),
            "data_processed": str(processed_root),
            "models": str(models_root),
            "reports": str(tmp / "reports"),
        }

        # 1. Build features from data/sample
        run_build_features(config, raw_root=DATA_SAMPLE, processed_root=processed_root)
        features_path = processed_root / "demo_real_v1" / "features.csv"
        assert features_path.exists(), "features.csv must be produced from data/sample"

        # 2. Train and save artifact
        run_id = run_training(
            config,
            processed_root=processed_root,
            models_root=models_root,
            dataset_version_hint="demo_real_v1",
        )
        assert run_id
        run_dir = models_root / run_id
        assert (run_dir / "model.keras").exists() or (run_dir / "saved_model").exists()
        assert (run_dir / "run_record.json").exists()

        # 3. Load artifact
        model, run_record = load_trained_model(run_dir)
        feature_columns = run_record.get("feature_columns", [])
        assert len(feature_columns) > 0

        # 4. One inference: one row from processed features, expected type and shape
        df = pd.read_csv(features_path)
        df = df[df["split"] == "train"].head(1)
        if df.empty:
            df = pd.read_csv(features_path).head(1)
        X_df = df[feature_columns].fillna(0)
        pred = predict_with_trained_model(model, run_record, X_df)

        assert isinstance(pred, np.ndarray)
        assert pred.ndim == 1
        assert pred.shape[0] == 1
        assert np.issubdtype(pred.dtype, np.floating)
        assert np.isfinite(float(pred[0]))
