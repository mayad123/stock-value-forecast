"""
Orchestration layer: workflows and CLI dispatch.

- run_cli(argv): full CLI entrypoint (used by run.py).
- run_stage(stage_name, config): run a single stage programmatically (CLI, tests, automation).
- Workflow functions (run_demo, run_demo_real, run_live) are in workflows module.
"""

from src.orchestration.entrypoint import run_cli, run_stage

__all__ = ["run_cli", "run_stage"]
