# Alpha Vantage API — Free-Tier Compliance

This project uses only **free-tier** Alpha Vantage endpoints and parameters. No code path issues premium-marked requests.

## Primary: Daily Prices (required for pipeline)

| Function | Purpose | Why free-tier compliant |
|----------|---------|--------------------------|
| **TIME_SERIES_DAILY** | Daily OHLCV for configured symbols | Free endpoint. We do **not** use TIME_SERIES_DAILY_ADJUSTED (premium). |

- **outputsize=compact** only (latest ~100 points). We never use `outputsize=full` (premium for daily).
- Daily price ingestion is the **primary** dataset and remains free-tier compliant.

## Optional Enrichment (additive; not required for training)

When enabled via config (`enrichment.*`), the following **non-premium** endpoints may be used (per official Alpha Vantage docs):

| Function | Purpose | Config flag |
|----------|---------|--------------|
| **SYMBOL_SEARCH** | Ticker discovery / validation | `enrichment.symbol_search` |
| **GLOBAL_QUOTE** | Current snapshot per symbol (sanity checks) | `enrichment.global_quote` |
| **TIME_SERIES_WEEKLY** | Weekly OHLCV (long-horizon context) | `enrichment.weekly_monthly` |
| **TIME_SERIES_MONTHLY** | Monthly OHLCV (long-horizon context) | `enrichment.weekly_monthly` |

Enrichment is **additive** and **never required** for training. Manifests record which enrichment data was collected (`manifest.enrichment`).

## What We Do Not Use

- **TIME_SERIES_DAILY_ADJUSTED** — Premium; not used.
- **outputsize=full** (for daily) — Premium; we use `compact` only.
- **Intraday** endpoints and realtime/delayed entitlement — Premium; not used.

## Implementation

- **Client:** `src/ingest/alphavantage.py` — Daily: `fetch_daily_raw()` only. Enrichment: `fetch_symbol_search`, `fetch_global_quote`, `fetch_weekly`, `fetch_monthly`. All use the same error/premium checks; premium responses raise `AlphaVantageError`.
- **Ingest:** `src/ingest/prices.py` — Primary: `fetch_daily_raw()` and ticker-level merge. Optional: `src/ingest/enrichment.run_enrichment()` when config flags are set; raw enrichment saved under `data/raw/enrichment/` and captured in manifest.

Free API key: [Alpha Vantage Support](https://www.alphavantage.co/support/#api-key). Limits: 5 requests/minute, 25/day.
