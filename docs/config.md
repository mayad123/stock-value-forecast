# Configuration

Configuration is centralized under `src.config`. All pipeline stages receive the same config dict.

## Resolution order

Applied in sequence:

1. **Static defaults** – `src.config.loader` defines minimal defaults (paths, tickers, time_horizon, etc.) so code never sees missing sections.

2. **YAML file** – A config file (e.g. `configs/recruiter_demo_real.yaml`) overrides defaults. Path may be absolute or relative to repo root. If the file is missing and a path was provided, a warning is logged (pipeline logger) and defaults are used.

3. **Runtime overrides** – The CLI sets `_config_path` on the config when a file path was provided (for reproducibility and run records).

4. **Secrets** – Never in YAML. API keys (`ALPHAVANTAGE_API_KEY`, `MARKETAUX_API_KEY`) are read from the environment at use-time via `src.config.secrets`. The serve layer uses env vars such as `SERVE_MODELS_PATH`, `MODEL_RUN_ID` for overrides.

## Usage

- **Load**: `from src.config import load_config; config = load_config("configs/live_apis.yaml")`
- **Validate**: `from src.config import validate_config; validate_config(config, require_mode=True)`
- **Secrets**: Use `get_api_keys(config)` or `require_live_apis_keys(config)` for live mode; keys come from `os.environ` only.

## Validation

`validate_config(config, require_mode=False)` checks:

- `paths` section with `data_processed`, `models`, `reports`
- `tickers.symbols` present (list of symbols)
- `time_horizon` and/or `feature_build` present
- If `require_mode=True`: `mode` must be one of `recruiter_demo`, `live_apis`

Invalid config raises `ConfigError` with a clear message. The orchestration layer validates after loading so missing or invalid config fails early.

## Typed accessors (optional)

`src.config.models` provides `get_paths_config(config)`, `get_tickers(config)`, `get_mode(config)` for typed access. Stages can keep using `config.get("paths", {})` etc.; the typed helpers document the shape and support IDE completion.
