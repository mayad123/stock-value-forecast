# Pipeline: two explicit workflows (demo | live) and single-stage targets
# Usage: make | make help | make demo | make live | make ingest | ...

PYTHON ?= python

.DEFAULT_GOAL := help

help:
	@echo "Workflows (explicit mode; no cross-mode):"
	@echo "  make demo   configs/recruiter_demo.yaml   build-features -> train -> backtest"
	@echo "              (offline, no ingest, no API keys)"
	@echo "  make live   configs/live_apis.yaml       ingest -> build-features -> train -> backtest"
	@echo "              (ingest prices + optional news, then features/train/backtest; requires API keys)"
	@echo ""
	@echo "Single stages (use with care; default config is recruiter_demo):"
	@echo "  make ingest  make build-features  make train  make backtest  make serve"
	@echo ""
	@echo "  make dev     start backend (port 8000) + UI (port 8501); Ctrl+C to stop both"
	@echo ""
	@echo "Dev: make lint  make test  make test-integration"

# CI-style checks (run before pushing)
lint:
	ruff check src tests run.py

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

test-integration:
	$(PYTHON) -m pytest tests/test_integration_e2e.py::test_e2e_build_features_produces_valid_artifacts_no_leakage -v --tb=short

# Demo: recruiter_demo.yaml only; never runs ingest
demo:
	$(PYTHON) run.py demo

# Live: live_apis.yaml; runs ingest (prices + optional news) then build-features -> train -> backtest
live:
	$(PYTHON) run.py live

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

# Start backend (background) + UI (foreground). Wait for backend health (60s timeout); on failure kill backend and exit. Ctrl+C stops both.
dev:
	@BACKEND_PID=; \
	trap 'kill $$BACKEND_PID 2>/dev/null; kill -9 $$(lsof -t -i:8000) 2>/dev/null; exit 0' INT TERM EXIT; \
	$(PYTHON) run.py serve & BACKEND_PID=$$!; \
	echo "Waiting for backend at http://localhost:8000/health (timeout 60s) ..."; \
	sh ./scripts/wait-for-backend.sh 60 $$BACKEND_PID || { kill $$BACKEND_PID 2>/dev/null; exit 1; }; \
	BACKEND_URL=http://localhost:8000 streamlit run frontend/app.py --server.port 8501 --server.address localhost

# Run all stages in order (uses default config)
pipeline: ingest build-features train backtest
	@echo "[PIPELINE] All stages completed."

.PHONY: help lint test test-integration demo live ingest build-features train backtest serve dev pipeline
