# Packaging and dependencies

## Source of truth

**`pyproject.toml`** is the single source of truth for the project:

- **Runtime:** `[project.dependencies]` — everything needed to run the pipeline, serve the API, and run the UI (PyYAML, pandas, TensorFlow, FastAPI, uvicorn, etc.).
- **Dev/test:** `[project.optional-dependencies].dev` — pytest, ruff. Install with `pip install -e ".[dev]"`.

## Install options

| Use case | Command |
|----------|---------|
| Local development (lint + tests) | `pip install -e ".[dev]"` |
| Runtime only (e.g. Docker, production) | `pip install -r requirements.txt` or `pip install .` |
| CI / “I prefer requirements files” | `pip install -r requirements-dev.txt` (includes runtime + pytest + ruff) |

## Files

- **`requirements.txt`** — Runtime deps only; mirrors `pyproject.toml` so Docker and simple installs work without installing the package. Kept in sync manually with `[project.dependencies]`.
- **`requirements-dev.txt`** — `-r requirements.txt` plus pytest and ruff. Alternative to `pip install -e ".[dev]"` when you don’t need an editable install.

## Entry point

After `pip install -e ".[dev]"` (or any install that includes the package), the CLI is available as:

```bash
stock-forecast demo
stock-forecast train
stock-forecast serve
# etc.
```

This is the same as `python run.py demo`; the entry point is defined in `pyproject.toml` as `[project.scripts] stock-forecast = "run:main"`.

## Build

The project uses setuptools (no separate setup.py). `pip install .` or `pip install -e ".[dev]"` uses the `[build-system]` and `[project]` sections in `pyproject.toml`. Lint and test config live in the same file (`[tool.ruff]`, `[tool.pytest.ini_options]`).
