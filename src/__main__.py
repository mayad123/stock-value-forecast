"""Allow python -m src --config CONFIG <stage> (same as python run.py --config CONFIG <stage>)."""
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import run  # noqa: E402
run.main()
