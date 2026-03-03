"""Tests for src.data.validate_prices_csv (schema, dates, numerics, summary artifact)."""

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def validate_module():
    from src.data.validate_prices_csv import (
        ValidationError,
        run_validate_prices,
        _process_one,
        _ordering_status,
    )
    return ValidationError, run_validate_prices, _process_one, _ordering_status


def test_ordering_status(validate_module):
    _, _, _, _ordering_status = validate_module
    import pandas as pd
    assert _ordering_status(pd.Series(["2024-01-01", "2024-01-02"])) == "ascending"
    assert _ordering_status(pd.Series(["2024-01-02", "2024-01-01"])) == "descending"
    assert _ordering_status(pd.Series(["2024-01-01", "2024-01-03", "2024-01-02"])) == "unsorted"


def test_process_one_missing_columns(validate_module):
    ValidationError, _, _process_one, _ = validate_module
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("ticker,date,open,high,low,close\n")  # missing adjusted_close, volume
        f.write("A,2024-01-01,1,1,1,1\n")
        path = Path(f.name)
    try:
        with pytest.raises(ValidationError, match="missing required columns"):
            _process_one(path, log=lambda m: None)
    finally:
        path.unlink(missing_ok=True)


def test_process_one_duplicate_dates_fails(validate_module):
    ValidationError, _, _process_one, _ = validate_module
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("ticker,date,open,high,low,close,adjusted_close,volume\n")
        f.write("A,2024-01-01,1,1,1,1,1,1\n")
        f.write("A,2024-01-01,2,2,2,2,2,2\n")
        path = Path(f.name)
    try:
        with pytest.raises(ValidationError, match="duplicate"):
            _process_one(path, log=lambda m: None)
    finally:
        path.unlink(missing_ok=True)


def test_process_one_descending_reversed_and_written(validate_module):
    _, _, _process_one, _ = validate_module
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("ticker,date,open,high,low,close,adjusted_close,volume\n")
        f.write("A,2024-01-03,1,1,1,1,1,1\n")
        f.write("A,2024-01-02,1,1,1,1,1,1\n")
        f.write("A,2024-01-01,1,1,1,1,1,1\n")
        path = Path(f.name)
    try:
        out = _process_one(path, log=lambda m: None, write_corrected=True)
        assert out["corrected"] is True
        assert out["min_date"] == "2024-01-01"
        assert out["max_date"] == "2024-01-03"
        lines = path.read_text().strip().split("\n")
        assert lines[1].startswith("A,2024-01-01,")
        assert lines[3].startswith("A,2024-01-03,")
    finally:
        path.unlink(missing_ok=True)


def test_process_one_missing_numeric_fails(validate_module):
    ValidationError, _, _process_one, _ = validate_module
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("ticker,date,open,high,low,close,adjusted_close,volume\n")
        f.write("A,2024-01-01,1,1,1,1,1,1\n")
        f.write("A,2024-01-02,,2,2,2,2,2\n")  # missing open
        path = Path(f.name)
    try:
        with pytest.raises(ValidationError, match="missing or non-numeric"):
            _process_one(path, log=lambda m: None)
    finally:
        path.unlink(missing_ok=True)


def test_run_validate_prices_produces_summary_artifact(validate_module):
    _, run_validate_prices, _, _ = validate_module
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "prices_normalized").mkdir(parents=True)
        (tmp / "reports").mkdir(parents=True)
        for name in ["X.csv", "Y.csv"]:
            (tmp / "prices_normalized" / name).write_text(
                "ticker,date,open,high,low,close,adjusted_close,volume\n"
                "A,2024-01-01,1,1,1,1,1,1\n"
                "A,2024-01-02,1,1,1,1,1,1\n"
            )
        config = {
            "paths": {"data_raw": str(tmp)},
            "feature_build": {"raw_dataset_version": "v1"},
        }
        out_path = run_validate_prices(
            config,
            raw_root=tmp,
            reports_path=tmp / "reports",
            dataset_version="v1",
            write_corrected=False,
            log=lambda m: None,
        )
        assert out_path.name == "data_validation_v1.json"
        assert out_path.exists()
        data = json.loads(out_path.read_text())
        assert data["dataset_version"] == "v1"
        assert set(data["tickers"]) == {"X", "Y"}
        assert data["row_counts"]["X"] == 2
        assert data["date_ranges"]["X"]["min"] == "2024-01-01"
        assert data["global_date_range"]["min"] == "2024-01-01"
