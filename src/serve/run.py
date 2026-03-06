"""Serve stage: load model and run prediction API with uvicorn."""


def run(config: dict) -> None:
    """Start the FastAPI service with uvicorn (model loaded at app startup)."""
    import os
    import uvicorn
    from src._cli import stage_log, stage_done

    stage_log("serve", "Starting API at http://127.0.0.1:8000")
    stage_done("serve")
    if os.environ.get("SERVE_DRY_RUN") == "1":
        return
    uvicorn.run(
        "src.serve.app:app",
        host="127.0.0.1",
        port=8000,
        reload=config.get("serve", {}).get("reload", False),
    )
