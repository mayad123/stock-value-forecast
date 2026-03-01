"""
Alpha Vantage API client for daily OHLCV data.
Free tier: 5 requests/minute, 25/day. Throttling and retries implemented.
"""

import os
import time
from typing import Any, Dict, Optional

# Minimum seconds between requests (5 per minute => 12s; use 13 for safety)
FREE_TIER_INTERVAL_SEC = 13

# Env var for API key
API_KEY_ENV = "ALPHAVANTAGE_API_KEY"

# Endpoint (daily adjusted = includes adjusted close)
BASE_URL = "https://www.alphavantage.co/query"


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


def fetch_daily_adjusted(
    symbol: str,
    api_key: str,
    outputsize: str = "full",
    session: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Fetch TIME_SERIES_DAILY_ADJUSTED for one symbol.
    Returns raw JSON as returned by the API (unchanged).
    Raises AlphaVantageError on missing/invalid key or unrecoverable rate limit.
    """
    import urllib.parse
    import urllib.request

    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "apikey": api_key,
        "outputsize": outputsize,
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)

    last_error: Optional[Exception] = None
    max_retries = 3
    retry_delays = [2, 5, 10]  # seconds

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
            data = __import__("json").loads(raw)

            # Check for API key / rate limit errors in body
            if _is_invalid_key_response(data):
                raise AlphaVantageError(
                    "Invalid API key. Check that ALPHAVANTAGE_API_KEY is correct. "
                    "Verify at https://www.alphavantage.co/support/#api-key"
                )
            if _is_rate_limit_response(data):
                if attempt == max_retries - 1:
                    raise AlphaVantageError(
                        "Rate limit exceeded and retries exhausted. "
                        "Free tier: 5 requests/minute, 25/day. Wait and try again later."
                    )
                time.sleep(retry_delays[attempt])
                continue

            # Success: return raw response unchanged
            return data
        except AlphaVantageError:
            raise
        except urllib.error.HTTPError as e:
            if e.code == 429:
                if attempt == max_retries - 1:
                    raise AlphaVantageError(
                        "Rate limit exceeded (HTTP 429) without recovery after retries."
                    ) from e
                time.sleep(retry_delays[attempt])
                continue
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


def throttle_wait() -> None:
    """Sleep to respect free-tier rate limit (5 req/min)."""
    time.sleep(FREE_TIER_INTERVAL_SEC)
