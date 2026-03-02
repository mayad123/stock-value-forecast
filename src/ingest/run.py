"""Ingest stage: fetch and persist raw price and optional news data."""

import sys
from pathlib import Path

# Allow running from repo root without installing package
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def run(config: dict) -> None:
    """Run the ingest pipeline: Alpha Vantage prices -> raw JSON + normalized + manifest."""
    if config.get("mode") == "recruiter_demo":
        print("Demo mode uses sample data. Use live_apis mode for ingestion.", file=sys.stderr)
        sys.exit(1)

    from src._cli import stage_log, stage_done
    from src.ingest.alphavantage import AlphaVantageError
    from src.ingest.prices import run_ingest_prices

    stage_log("ingest", "Loading config")
    tickers = config.get("tickers", {}).get("symbols", [])
    stage_log("ingest", f"Tickers universe: {len(tickers)} symbols")

    try:
        run_ingest_prices(
            config,
            log=lambda msg: stage_log("ingest", msg),
        )
    except AlphaVantageError as e:
        stage_log("ingest", f"Fatal: {e}")
        sys.exit(1)

    if config.get("use_news"):
        try:
            from src.ingest.news import run_ingest_news
            from src.ingest.marketaux import MarketauxError
            run_ingest_news(config, log=lambda msg: stage_log("ingest", msg))
        except MarketauxError as e:
            stage_log("ingest", f"News ingest fatal: {e}")
            sys.exit(1)
    stage_done("ingest")
