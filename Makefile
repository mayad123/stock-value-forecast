# Pipeline stages and dev targets
# Usage: make lint | make test | make ingest | make build-features | ...

PYTHON ?= python

# CI-style checks (run before pushing)
lint:
	ruff check src tests run.py

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

test-integration:
	$(PYTHON) -m pytest tests/test_integration_e2e.py::test_e2e_build_features_produces_valid_artifacts_no_leakage -v --tb=short

ingest:
	$(PYTHON) run.py ingest

build-features:
	$(PYTHON) run.py build-features

train:
	$(PYTHON) run.py train

backtest:
	$(PYTHON) run.py backtest

serve:
	$(PYTHON) run.py serve

# Run all stages in order (stubs only)
pipeline: ingest build-features train backtest
	@echo "[PIPELINE] All stages completed (stubs)."

.PHONY: lint test test-integration ingest build-features train backtest serve pipeline
