#!/usr/bin/env bash
# Run demo-real pipeline using the repo venv and env vars that prevent TensorFlow locking.
# From repo root: ./scripts/run-demo-real.sh
# Or: bash scripts/run-demo-real.sh

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Prefer venv in repo root so TensorFlow is only in venv, not global
if [ -x "./venv/bin/python" ]; then
  PYTHON="./venv/bin/python"
elif [ -n "$VIRTUAL_ENV" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
  PYTHON="$VIRTUAL_ENV/bin/python"
else
  PYTHON="python3"
fi

export CUDA_VISIBLE_DEVICES=""
export TF_CPP_MIN_LOG_LEVEL="3"
export TF_NUM_INTEROP_THREADS="1"
export TF_NUM_INTRAOP_THREADS="1"

echo "[run-demo-real] Using: $PYTHON"
"$PYTHON" run.py demo-real
