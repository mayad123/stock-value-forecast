# Logging

Pipeline and serve logging use a single strategy so output is consistent and easy to operate.

## Strategy

- **Library**: Python standard `logging`. No external observability stack.
- **Format**: `[COMPONENT] message` (e.g. `[INGEST] Loading config`, `[TRAIN] Done.`).
- **Destination**: Logs go to **stderr** so stdout can stay clean for scripts.
- **Level**: `INFO` by default. Set `LOG_LEVEL=DEBUG` for verbose output (e.g. artifact resolution).

## Components

Stage and component names are normalized to uppercase in the log prefix:

- **Stages**: `ingest`, `build-features`, `train`, `backtest`, `serve`, `feature-importance`
- **CLI/orchestration**: `cli`, `workflow`, `config`
- **Serve**: `serve` (model loading, artifact resolution, feature load)

## Usage in code

- **Stage progress**: Use `stage_log(stage, message)` and `stage_done(stage)` from `src._cli` (backed by `src.logging_config`).
- **Direct logging**: `from src.logging_config import get_logger; log = get_logger("serve"); log.info("...")`.
- **Default log callbacks**: Domain modules (train, backtest, feature_importance, etc.) use `get_logger(component)` when no `log` callback is passed, so all progress goes through the same pipeline logger.

## Failures

- **User-facing errors**: Logged at ERROR with a clear message before exit or re-raise. Exceptions (e.g. `ConfigError`, `FileNotFoundError` from artifact resolution) include actionable hints (e.g. "Run: python run.py train").
- **Real exceptions**: Not buried; critical paths log and re-raise so stack traces are available when `LOG_LEVEL=DEBUG` or when the exception propagates.
