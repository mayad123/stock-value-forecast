"""Tests for src.core (paths, package boundary)."""

from src.core.paths import get_paths, repo_root


def test_repo_root_returns_path():
    root = repo_root()
    assert root is not None
    assert root.is_dir()
    assert (root / "run.py").exists()
    assert (root / "src").is_dir()


def test_repo_root_matches_conftest(project_root):
    """repo_root() returns the same path as the pytest project_root fixture."""
    assert repo_root() == project_root


def test_get_paths_returns_expected_keys(project_root):
    config = {
        "paths": {
            "data_processed": "data/processed",
            "models": "models",
            "reports": "reports",
            "data_raw": "data/sample",
        }
    }
    paths = get_paths(config)
    assert "repo_root" in paths
    assert "processed_path" in paths
    assert "models_path" in paths
    assert "reports_path" in paths
    assert "data_raw" in paths
    assert paths["repo_root"] == project_root
    assert paths["processed_path"] == paths["repo_root"] / "data" / "processed"
    assert paths["models_path"] == paths["repo_root"] / "models"
    assert paths["reports_path"] == paths["repo_root"] / "reports"


def test_get_paths_defaults_when_paths_empty():
    paths = get_paths({})
    assert paths["processed_path"] == paths["repo_root"] / "data" / "processed"
    assert paths["models_path"] == paths["repo_root"] / "models"
    assert paths["reports_path"] == paths["repo_root"] / "reports"


def test_data_versioning_importable():
    """Ensure src.data.versioning is the single source for resolve_processed_version."""
    from src.data.versioning import resolve_processed_version

    assert callable(resolve_processed_version)


def test_config_package_importable():
    """Ensure src.config re-exports from _cli for clean package boundary."""
    from src.config import load_config

    assert callable(load_config)
    config = load_config(None)
    assert isinstance(config, dict)
