"""Tests for src.data.manifest (generate manifest from prices_normalized CSVs)."""

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def manifest_module():
    """Import after conftest has set sys.path (avoids collection-time ModuleNotFoundError in CI)."""
    from src.data.manifest import generate_manifest, _scan_csv_dates
    return generate_manifest, _scan_csv_dates


def test_scan_csv_dates(manifest_module):
    generate_manifest, _scan_csv_dates = manifest_module
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write("ticker,date,open,high,low,close,adjusted_close,volume\n")
        f.write("AAPL,2024-01-02,1,1,1,1,1,1\n")
        f.write("AAPL,2024-01-05,1,1,1,1,1,1\n")
        path = Path(f.name)
    try:
        ticker, n, min_d, max_d = _scan_csv_dates(path)
        assert ticker == path.stem
        assert n == 2
        assert min_d == "2024-01-02"
        assert max_d == "2024-01-05"
    finally:
        path.unlink(missing_ok=True)


def test_generate_manifest_includes_all_csvs_and_date_range(manifest_module):
    generate_manifest, _ = manifest_module
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "prices_normalized").mkdir()
        (tmp / "manifests").mkdir()
        for name, dates in [("AAPL.csv", ("2024-01-02", "2024-01-10")), ("MSFT.csv", ("2024-01-05", "2024-01-15"))]:
            (tmp / "prices_normalized" / name).write_text(
                "ticker,date,open,high,low,close,adjusted_close,volume\n"
                f"A,{dates[0]},1,1,1,1,1,1\n"
                f"A,{dates[1]},1,1,1,1,1,1\n"
            )
        out = generate_manifest(tmp, "test_v1", log=lambda m: None)
        assert out.name == "test_v1.json" and out.parent.name == "manifests"
        data = json.loads(out.read_text())
        assert data["dataset_version"] == "test_v1"
        assert set(data["tickers"]) == {"AAPL", "MSFT"}
        assert data["date_range"]["min"] == "2024-01-02"
        assert data["date_range"]["max"] == "2024-01-15"
        assert "prices_normalized/AAPL.csv" in data["normalized_paths"]
        assert "prices_normalized/MSFT.csv" in data["normalized_paths"]
        assert len(data["normalized_paths"]) == 2
        for p in data["normalized_paths"]:
            assert (tmp / p).exists()


def test_generate_manifest_fails_no_csvs(manifest_module):
    generate_manifest, _ = manifest_module
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "prices_normalized").mkdir()
        with pytest.raises(FileNotFoundError, match="No \\*\\.csv"):
            generate_manifest(tmp, "v", log=lambda m: None)
