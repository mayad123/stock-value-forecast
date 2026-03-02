"""
Pytest configuration. Adds repo root to sys.path and loads .env when present so
local test runs can use API keys (e.g. for manual integration tests). Tests that
need to assert on missing/invalid keys override env in the test (e.g. patch.dict(os.environ, ...)).
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def pytest_configure(config):
    """Load .env from repo root before any tests run."""
    try:
        from dotenv import load_dotenv
        load_dotenv(_REPO_ROOT / ".env")
    except ImportError:
        pass
