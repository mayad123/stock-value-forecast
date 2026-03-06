"""Tests for centralized artifact path resolution (src.core.artifacts)."""

import pytest

from src.core.artifacts import (
    ResolvedRun,
    deploy_artifacts_models_path,
    resolve_features_path,
    resolve_report_path,
    resolve_run,
    resolve_run_dir,
    run_id_from_version,
)


def test_run_id_from_version():
    """run_id_from_version produces stable format with version prefix and UTC timestamp."""
    run_id = run_id_from_version("demo_real_v1")
    assert run_id.startswith("demo_real_v1_")
    assert "T" in run_id and "Z" in run_id


def test_resolve_run_dir_by_hint(tmp_path):
    """resolve_run_dir returns run_dir when run_id_hint matches a valid run."""
    (tmp_path / "v1_20240101T120000Z").mkdir(parents=True)
    run_dir = tmp_path / "v1_20240101T120000Z"
    (run_dir / "model.keras").touch()
    (run_dir / "run_record.json").write_text("{}")
    resolved = resolve_run_dir(tmp_path, "v1", run_id_hint="v1_20240101T120000Z")
    assert resolved == run_dir


def test_resolve_run_dir_latest_by_version(tmp_path):
    """resolve_run_dir returns latest run dir for dataset_version when no hint."""
    for name in ["v1_20240101T120000Z", "v1_20240102T120000Z"]:
        d = tmp_path / name
        d.mkdir(parents=True)
        (d / "model.keras").touch()
        (d / "run_record.json").write_text("{}")
    resolved = resolve_run_dir(tmp_path, "v1")
    assert resolved.name == "v1_20240102T120000Z"


def test_resolve_run_dir_raises_when_empty(tmp_path):
    """resolve_run_dir raises FileNotFoundError when no valid run."""
    with pytest.raises(FileNotFoundError, match="No trained model"):
        resolve_run_dir(tmp_path, "v1")


def test_resolve_run_returns_resolved_run(tmp_path):
    """resolve_run returns ResolvedRun with run_id and run_dir."""
    (tmp_path / "v1_20240101T120000Z").mkdir(parents=True)
    run_dir = tmp_path / "v1_20240101T120000Z"
    (run_dir / "model.keras").touch()
    (run_dir / "run_record.json").write_text("{}")
    result = resolve_run(tmp_path, "v1", run_id_hint="v1_20240101T120000Z")
    assert isinstance(result, ResolvedRun)
    assert result.run_id == "v1_20240101T120000Z"
    assert result.run_dir == run_dir


def test_resolve_features_path_primary(tmp_path):
    """resolve_features_path returns primary path when it exists."""
    processed = tmp_path / "processed"
    (processed / "v1").mkdir(parents=True)
    (processed / "v1" / "features.csv").write_text("a,b\n1,2\n")
    repo = tmp_path
    path = resolve_features_path(processed, "v1", repo)
    assert path.exists()
    assert path == processed / "v1" / "features.csv"


def test_resolve_features_path_fallback_demo(tmp_path):
    """resolve_features_path falls back to deploy_artifacts/processed/demo when primary missing."""
    processed = tmp_path / "processed"
    processed.mkdir(parents=True)
    deploy = tmp_path / "deploy_artifacts" / "processed" / "demo"
    deploy.mkdir(parents=True)
    (deploy / "features.csv").write_text("a,b\n1,2\n")
    path = resolve_features_path(processed, "v1", tmp_path)
    assert path.exists()
    assert "demo" in str(path)


def test_resolve_report_path_fallback(tmp_path):
    """resolve_report_path falls back to deploy_artifacts/reports when primary missing."""
    reports = tmp_path / "reports"
    reports.mkdir(parents=True)
    deploy = tmp_path / "deploy_artifacts" / "reports"
    deploy.mkdir(parents=True)
    (deploy / "latest_metrics.json").write_text("{}")
    path = resolve_report_path(reports, "latest_metrics.json", tmp_path)
    assert path.exists()
    assert "deploy_artifacts" in str(path)


def test_deploy_artifacts_models_path():
    """deploy_artifacts_models_path returns repo_root/deploy_artifacts/models."""
    from src.core.paths import repo_root
    p = deploy_artifacts_models_path(repo_root())
    assert p.name == "models"
    assert "deploy_artifacts" in str(p)
