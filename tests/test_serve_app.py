"""Tests for the FastAPI serving layer (health, model_info, predict from stored artifact)."""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Optional: skip if no fastapi/uvicorn
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


def _make_serve_artifact(tmp_path: Path) -> None:
    """Create minimal model dir and processed features for serve tests."""
    run_id = "test_serve_run"
    run_dir = tmp_path / "models" / run_id
    run_dir.mkdir(parents=True)
    # Minimal SavedModel (TensorFlow)
    tf = pytest.importorskip("tensorflow")
    model = tf.keras.Sequential([
        tf.keras.layers.Input(shape=(7,)),
        tf.keras.layers.Dense(4, activation="relu"),
        tf.keras.layers.Dense(1, activation="tanh"),
    ])
    model.save(run_dir / "model.keras")
    run_record = {
        "run_id": run_id,
        "dataset_version": "v1",
        "feature_columns": [
            "return_1d", "return_5d", "return_21d",
            "volatility_5d", "volatility_21d", "range_hl", "volume_pct_1d",
        ],
        "scaler": {"mean": [0.0] * 7, "scale": [1.0] * 7},
        "split_boundaries": {"train_end": "2024-01-24", "val_start": "2024-01-25"},
    }
    (run_dir / "run_record.json").write_text(json.dumps(run_record, indent=2))
    # Processed features for lookup
    proc = tmp_path / "data" / "processed" / "v1"
    proc.mkdir(parents=True)
    csv = (
        "ticker,date,split,return_1d,return_5d,return_21d,volatility_5d,volatility_21d,range_hl,volume_pct_1d,target_forward_return\n"
        "AAPL,2024-01-22,train,0.01,0.02,0.03,0.01,0.01,0.01,0.0,0.01\n"
        "AAPL,2024-01-25,val,0.02,0.01,0.02,0.01,0.01,0.01,0.0,0.015\n"
    )
    (proc / "features.csv").write_text(csv)


@pytest.fixture
def serve_client():
    """TestClient with env pointing to a minimal model and processed data."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        _make_serve_artifact(tmp)
        env = {
            "SERVE_MODELS_PATH": str(tmp / "models"),
            "SERVE_PROCESSED_PATH": str(tmp / "data" / "processed"),
            "MODEL_RUN_ID": "test_serve_run",
        }
        prev = {k: os.environ.get(k) for k in env}
        for k, v in env.items():
            os.environ[k] = v
        try:
            from src.serve.app import app
            with TestClient(app) as client:
                yield client
        finally:
            for k in env:
                if prev.get(k) is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = prev[k]


def test_health(serve_client):
    r = serve_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_model_info(serve_client):
    r = serve_client.get("/model_info")
    assert r.status_code == 200
    data = r.json()
    assert data["model_version"] == "test_serve_run"
    assert data["dataset_version"] == "v1"
    assert data["num_features"] == 7
    assert "feature_schema_fingerprint" in data
    assert len(data["feature_schema_fingerprint"]) == 16
    assert "training_window" in data
    assert data["feature_columns"] == [
        "return_1d", "return_5d", "return_21d",
        "volatility_5d", "volatility_21d", "range_hl", "volume_pct_1d",
    ]


def test_predict(serve_client):
    r = serve_client.post(
        "/predict",
        json={"ticker": "AAPL", "as_of": "2024-01-26", "horizon": 1},
    )
    assert r.status_code == 200
    data = r.json()
    assert "prediction" in data
    assert "confidence" in data
    assert data["ticker"] == "AAPL"
    assert data["as_of"] == "2024-01-25"  # latest date <= as_of
    assert data.get("model_version") == "test_serve_run"
    assert 0 <= data["confidence"] <= 1
    assert -1 <= data["prediction"] <= 1


def test_predict_validation_rejects_empty_ticker(serve_client):
    r = serve_client.post(
        "/predict",
        json={"ticker": "", "as_of": "2024-01-26", "horizon": 1},
    )
    assert r.status_code == 422


def test_predict_404_when_no_features(serve_client):
    r = serve_client.post(
        "/predict",
        json={"ticker": "UNKNOWN", "as_of": "2020-01-01", "horizon": 1},
    )
    assert r.status_code == 404


def test_predict_400_when_features_missing_or_extra(serve_client):
    """Request with missing or extra features returns 400 with expected vs received."""
    # Missing feature
    r = serve_client.post(
        "/predict",
        json={
            "ticker": "AAPL",
            "as_of": "2024-01-26",
            "features": {
                "return_1d": 0.01,
                "return_5d": 0.02,
                "return_21d": 0.03,
                "volatility_5d": 0.01,
                "volatility_21d": 0.01,
                "range_hl": 0.01,
            },
        },
    )
    assert r.status_code == 400
    data = r.json()
    assert "detail" in data
    assert "expected vs received" in data["detail"].lower() or "expected" in data["detail"].lower()
    assert "missing" in data["detail"].lower()

    # Extra feature
    r = serve_client.post(
        "/predict",
        json={
            "ticker": "AAPL",
            "as_of": "2024-01-26",
            "features": {
                "return_1d": 0.01,
                "return_5d": 0.02,
                "return_21d": 0.03,
                "volatility_5d": 0.01,
                "volatility_21d": 0.01,
                "range_hl": 0.01,
                "volume_pct_1d": 0.0,
                "extra_col": 1.0,
            },
        },
    )
    assert r.status_code == 400
    data = r.json()
    assert "detail" in data
    assert "extra" in data["detail"].lower()


def test_predict_200_with_valid_features_mapping(serve_client):
    """Valid request with features dict returns 200 and includes model_version."""
    r = serve_client.post(
        "/predict",
        json={
            "ticker": "AAPL",
            "as_of": "2024-01-26",
            "features": {
                "return_1d": 0.01,
                "return_5d": 0.02,
                "return_21d": 0.03,
                "volatility_5d": 0.01,
                "volatility_21d": 0.01,
                "range_hl": 0.01,
                "volume_pct_1d": 0.0,
            },
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "prediction" in data
    assert data.get("model_version") == "test_serve_run"
    assert -1 <= data["prediction"] <= 1
