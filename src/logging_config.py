"""
Pipeline logging: one place for format and level.

Uses standard library logging. Stage messages look like [INGEST] message.
Set LOG_LEVEL=DEBUG for verbose output (e.g. artifact resolution).
"""

import logging
import os
import sys

# Logger name for pipeline stages and components
PIPELINE_LOGGER_NAME = "pipeline"

# Default level; override with LOG_LEVEL=DEBUG or LOG_LEVEL=INFO
_default_level = os.environ.get("LOG_LEVEL", "INFO").upper()
_level = getattr(logging, _default_level, logging.INFO)


class PipelineFormatter(logging.Formatter):
    """Format as [COMPONENT] message. Component comes from LoggerAdapter extra."""

    def format(self, record: logging.LogRecord) -> str:
        component = getattr(record, "component", "PIPELINE")
        msg = record.getMessage()
        return f"[{component}] {msg}"


def _ensure_handler() -> None:
    logger = logging.getLogger(PIPELINE_LOGGER_NAME)
    if logger.handlers:
        return
    logger.setLevel(_level)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(PipelineFormatter())
    logger.addHandler(handler)
    logger.propagate = False


def get_logger(component: str) -> logging.LoggerAdapter:
    """
    Return a logger for a pipeline component (ingest, build-features, train, backtest, serve, config, etc.).
    Messages are formatted as [COMPONENT] message. Component is uppercased for display.
    """
    _ensure_handler()
    base = logging.getLogger(PIPELINE_LOGGER_NAME)
    return logging.LoggerAdapter(base, {"component": component.upper()})


def get_pipeline_logger() -> logging.Logger:
    """Return the raw pipeline logger (use with LoggerAdapter for component prefix)."""
    _ensure_handler()
    return logging.getLogger(PIPELINE_LOGGER_NAME)


def stage_log(stage: str, message: str) -> None:
    """Emit a stage progress line. Replaces ad hoc print([STAGE] msg)."""
    get_logger(stage).info(message)


def stage_done(stage: str) -> None:
    """Emit stage completion. Use at end of each pipeline stage."""
    get_logger(stage).info("Done.")
