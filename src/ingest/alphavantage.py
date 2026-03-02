"""
Alpha Vantage API client: daily OHLCV (primary) and optional free-tier enrichment.
Primary: TIME_SERIES_DAILY with outputsize=compact. Enrichment: SYMBOL_SEARCH, GLOBAL_QUOTE,
TIME_SERIES_WEEKLY, TIME_SERIES_MONTHLY (all non-premium per official docs). Throttling and retries.
"""

import os
import time
from typing import Any, Dict, Optional

# Minimum seconds between requests (5 per minute => 12s; use 13 for safety)
FREE_TIER_INTERVAL_SEC = 13

# Env var for API key
API_KEY_ENV = "ALPHAVANTAGE_API_KEY"

# Endpoint — free-tier daily only (no TIME_SERIES_DAILY_ADJUSTED, no outputsize=full)
BASE_URL = "https://www.alphavantage.co/query"

# Free-tier function and output size (compact = last ~100 days; full is premium for daily)
FUNCTION_DAILY = "TIME_SERIES_DAILY"
OUTPUTSIZE_COMPACT = "compact"


class AlphaVantageError(Exception):
    """Raised when the API key is missing, invalid, or rate limit exceeded without recovery."""

    pass


def get_api_key() -> str:
    """Read API key from environment. Raises AlphaVantageError if missing."""
    key = os.environ.get(API_KEY_ENV, "").strip()
    if not key:
        raise AlphaVantageError(
            f"Missing API key. Set the {API_KEY_ENV} environment variable. "
            "Get a free key at https://www.alphavantage.co/support/#api-key"
        )
    return key


def _is_rate_limit_response(data: Dict[str, Any]) -> bool:
    """True if response indicates rate limit (free tier)."""
    if not isinstance(data, dict):
        return False
    # API often returns note about rate limit in "Note" or "Information"
    note = (data.get("Note") or data.get("Information") or "").lower()
    return "rate limit" in note or "call frequency" in note or "5 calls per minute" in note


def _is_invalid_key_response(data: Dict[str, Any]) -> bool:
    """True if response indicates invalid API key."""
    if not isinstance(data, dict):
        return False
    msg = (data.get("Note") or data.get("Information") or "").lower()
    return "invalid" in msg and "api key" in msg


def _is_premium_response(data: Dict[str, Any]) -> bool:
    """True if response indicates a premium-only endpoint was requested."""
    if not isinstance(data, dict):
        return False
    msg = (data.get("Note") or data.get("Information") or "").lower()
    return "premium" in msg and "endpoint" in msg


def _request(params: Dict[str, str]) -> Dict[str, Any]:
    """
    Execute one Alpha Vantage GET request; validate for key/rate-limit/premium errors.
    Returns parsed JSON. Raises AlphaVantageError on invalid key, premium response, or unrecoverable rate limit.
    """
    import urllib.parse
    import urllib.request

    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    last_error: Optional[Exception] = None
    max_retries = 3
    retry_delays = [2, 5, 10]

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
            data = __import__("json").loads(raw)
            if _is_invalid_key_response(data):
                raise AlphaVantageError(
                    "Invalid API key. Check that ALPHAVANTAGE_API_KEY is correct. "
                    "Verify at https://www.alphavantage.co/support/#api-key"
                )
            if _is_premium_response(data):
                raise AlphaVantageError(
                    "Alpha Vantage returned a premium-endpoint response. This code uses only free-tier endpoints."
                )
            if _is_rate_limit_response(data):
                if attempt == max_retries - 1:
                    raise AlphaVantageError(
                        "Rate limit exceeded and retries exhausted. "
                        "Free tier: 5 requests/minute, 25/day. Wait and try again later."
                    )
                time.sleep(retry_delays[attempt])
                continue
            return data
        except AlphaVantageError:
            raise
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(retry_delays[attempt])
                continue
            if e.code == 429:
                raise AlphaVantageError("Rate limit exceeded (HTTP 429) without recovery after retries.") from e
            if e.code == 401:
                raise AlphaVantageError("API key rejected (HTTP 401).") from e
            last_error = e
            if attempt < max_retries - 1 and e.code >= 500:
                time.sleep(retry_delays[attempt])
                continue
            raise
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(retry_delays[attempt])
                continue
            raise AlphaVantageError(f"Request failed after {max_retries} retries.") from last_error
    raise AlphaVantageError("Request failed.") from last_error


def fetch_daily_raw(
    symbol: str,
    api_key: str,
    session: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Fetch daily raw candles: TIME_SERIES_DAILY (free tier) with outputsize=compact (latest ~100 points).
    Daily adjusted is not used by the pipeline; this is the only daily fetch method.
    Returns raw JSON as returned by the API (unchanged).
    """
    return _request({
        "function": FUNCTION_DAILY,
        "symbol": symbol,
        "apikey": api_key,
        "outputsize": OUTPUTSIZE_COMPACT,
    })


# --- Optional enrichment (free-tier; not premium per official docs) ---

def fetch_symbol_search(keywords: str, api_key: str) -> Dict[str, Any]:
    """SYMBOL_SEARCH: ticker discovery/validation. Free utility endpoint."""
    return _request({"function": "SYMBOL_SEARCH", "keywords": keywords, "apikey": api_key})


def fetch_global_quote(symbol: str, api_key: str) -> Dict[str, Any]:
    """GLOBAL_QUOTE: lightweight current snapshot for one symbol. Free time series utility."""
    return _request({"function": "GLOBAL_QUOTE", "symbol": symbol, "apikey": api_key})


def fetch_weekly(symbol: str, api_key: str) -> Dict[str, Any]:
    """TIME_SERIES_WEEKLY: weekly OHLCV (compact, no outputsize=full). Free; not premium in docs."""
    return _request({
        "function": "TIME_SERIES_WEEKLY",
        "symbol": symbol,
        "apikey": api_key,
    })


def fetch_monthly(symbol: str, api_key: str) -> Dict[str, Any]:
    """TIME_SERIES_MONTHLY: monthly OHLCV (compact). Free; not premium in docs."""
    return _request({
        "function": "TIME_SERIES_MONTHLY",
        "symbol": symbol,
        "apikey": api_key,
    })


def throttle_wait() -> None:
    """Sleep to respect free-tier rate limit (5 req/min)."""
    time.sleep(FREE_TIER_INTERVAL_SEC)
