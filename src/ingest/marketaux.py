"""
Marketaux API client for financial news.
Free tier: rate limits apply (429 = too many in 60s; 402 = usage limit). Throttling and retries implemented.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

BASE_URL = "https://api.marketaux.com/v1/news/all"
API_KEY_ENV = "MARKETAUX_API_KEY"
# Conservative: 1 request per 2 seconds to stay under free-tier rate limits
FREE_TIER_INTERVAL_SEC = 2.0


class MarketauxError(Exception):
    """Raised when API key is missing, invalid, or rate/usage limit exceeded without recovery."""

    pass


def get_api_key() -> str:
    """Read API key from environment. Raises MarketauxError if missing."""
    key = os.environ.get(API_KEY_ENV, "").strip()
    if not key:
        raise MarketauxError(
            f"Missing API key. Set the {API_KEY_ENV} environment variable. "
            "Get a free key at https://www.marketaux.com/register"
        )
    return key


def _is_error_response(data: Dict[str, Any]) -> tuple:
    """Returns (is_error, error_message)."""
    if not isinstance(data, dict):
        return False, ""
    err = data.get("error") or data.get("message") or ""
    code = data.get("code")
    if code == 401 or "invalid" in str(err).lower() and "token" in str(err).lower():
        return True, "Invalid API token. Check that MARKETAUX_API_KEY is correct."
    if code == 402:
        return True, "Usage limit of your plan has been reached. Check MARKETAUX dashboard."
    if code == 429:
        return True, "Rate limit exceeded (too many requests in 60 seconds)."
    if err:
        return True, str(err)
    return False, ""


def fetch_news(
    api_key: str,
    symbols: Optional[List[str]] = None,
    published_after: Optional[str] = None,
    published_before: Optional[str] = None,
    limit: int = 50,
    page: int = 1,
    language: str = "en",
    filter_entities: bool = True,
    session: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Fetch one page of news from Marketaux. Returns raw JSON unchanged.
    Raises MarketauxError on missing/invalid key or unrecoverable rate/usage limit.
    """
    params: Dict[str, str] = {
        "api_token": api_key,
        "language": language,
        "limit": str(min(max(1, limit), 100)),
        "page": str(max(1, page)),
    }
    if symbols:
        params["symbols"] = ",".join(s.strip().upper() for s in symbols)
    if published_after:
        params["published_after"] = published_after
    if published_before:
        params["published_before"] = published_before
    if filter_entities:
        params["filter_entities"] = "true"

    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    last_error: Optional[Exception] = None
    max_retries = 3
    retry_delays = [2, 5, 10]

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            is_err, msg = _is_error_response(data)
            if is_err:
                if attempt == max_retries - 1:
                    raise MarketauxError(msg)
                time.sleep(retry_delays[attempt])
                continue
            return data
        except MarketauxError:
            raise
        except urllib.error.HTTPError as e:
            if e.code == 429:
                if attempt == max_retries - 1:
                    raise MarketauxError(
                        "Rate limit exceeded (HTTP 429) without recovery after retries."
                    ) from e
                time.sleep(retry_delays[attempt])
                continue
            if e.code == 402:
                raise MarketauxError(
                    "Usage limit reached (HTTP 402). Check your Marketaux plan."
                ) from e
            if e.code == 401:
                raise MarketauxError("API token rejected (HTTP 401).") from e
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
            raise MarketauxError(f"Request failed after {max_retries} retries.") from last_error

    raise MarketauxError("Request failed.") from last_error


def throttle_wait() -> None:
    """Sleep to respect free-tier rate limit."""
    time.sleep(FREE_TIER_INTERVAL_SEC)
