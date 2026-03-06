"""Ingest stage: fetch and persist raw price and optional news data."""

import sys

from src._cli import stage_done, stage_log
from src.ingest.service import run_ingest


def run(config: dict) -> None:
    """CLI entry: run ingest service; exit with clear message on failure."""
    from src.ingest.alphavantage import AlphaVantageError
    from src.ingest.marketaux import MarketauxError

    stage_log("ingest", "Loading config")
    tickers = config.get("tickers", {}).get("symbols", [])
    stage_log("ingest", f"Tickers universe: {len(tickers)} symbols")

    try:
        run_ingest(config, log=lambda msg: stage_log("ingest", msg))
    except ValueError as e:
        stage_log("ingest", str(e))
        sys.exit(1)
    except AlphaVantageError as e:
        stage_log("ingest", f"Fatal: {e}")
        sys.exit(1)
    except MarketauxError as e:
        stage_log("ingest", f"Fatal: {e}")
        sys.exit(1)
    stage_done("ingest")
