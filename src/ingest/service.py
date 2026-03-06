"""
Ingestion service: single entry point for price and optional news ingest.

Inputs: config dict, optional log callback, optional path overrides.
Outputs: None (writes to data/raw); raises on invalid mode or API errors.
No global state; safe to call from orchestration or tests.
"""

from typing import Any, Callable, Dict, Optional


def run_ingest(
    config: Dict[str, Any],
    *,
    log: Optional[Callable[[str], None]] = None,
    data_raw_root: Optional[Any] = None,
) -> None:
    """
    Run full ingest: prices then optional news. Uses config paths and tickers.

    Raises:
        ValueError: if mode is recruiter_demo (use sample data; no ingest).
        AlphaVantageError: on price API failure.
        MarketauxError: on news API failure when use_news is True.
    """
    if config.get("mode") == "recruiter_demo":
        raise ValueError(
            "Demo mode uses sample data. Use live_apis mode for ingestion."
        )

    from src.ingest.alphavantage import AlphaVantageError
    from src.ingest.prices import run_ingest_prices

    run_ingest_prices(
        config,
        data_raw_root=data_raw_root,
        log=log,
    )

    if config.get("use_news"):
        from src.ingest.marketaux import MarketauxError
        from src.ingest.news import run_ingest_news

        run_ingest_news(
            config,
            data_raw_root=data_raw_root,
            log=log,
        )
