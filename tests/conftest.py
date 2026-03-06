"""
Pytest configuration. Adds project root to sys.path and loads .env when present.
Tests that need the project root can use the project_root fixture.
"""

import sys
from pathlib import Path

import pytest

# Project root (parent of tests/)
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def pytest_configure(config):
    """Load .env from repo root before any tests run."""
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass


@pytest.fixture
def project_root():
    """Project root path for tests that need to resolve config paths or run subprocesses."""
    return REPO_ROOT
