"""
Backend API client: all HTTP calls to the serve layer.

No Streamlit; returns data or error strings. Caller handles session state and UI.
"""

from typing import Any, Dict, List, Optional, Tuple

import requests


def get_health(base_url: str, timeout: int = 60) -> bool:
    """Return True if GET /health returns 200."""
    if not (base_url or "").strip():
        return False
    try:
        r = requests.get(f"{base_url.rstrip('/')}/health", timeout=timeout)
        return r.ok
    except requests.RequestException:
        return False


def get_prediction_options(base_url: str, timeout: int = 60) -> Tuple[Optional[Dict], Optional[str]]:
    """GET /prediction_options. Returns (data, None) or (None, error_message)."""
    if not (base_url or "").strip():
        return None, "Backend not configured. Set BACKEND_URL."
    try:
        r = requests.get(f"{base_url.rstrip('/')}/prediction_options", timeout=timeout)
        if not r.ok:
            return None, f"Backend returned {r.status_code}"
        data = r.json() if r.text else {}
        if not isinstance(data, dict):
            data = {}
        if not data.get("tickers") and not data.get("dates_by_ticker"):
            return data, "Backend returned no tickers/dates. Ensure processed data exists."
        return data, None
    except requests.RequestException as e:
        return None, f"Request failed: {e}"


def get_metrics(base_url: str, timeout: int = 60) -> Tuple[Optional[Dict], Optional[str]]:
    """GET /metrics. Returns (data, None) or (None, error_message). data is always a dict when success."""
    try:
        r = requests.get(f"{base_url.rstrip('/')}/metrics", timeout=timeout)
        if not r.ok:
            return None, f"/metrics returned {r.status_code}"
        data = r.json() if r.text else None
        if data is not None and not isinstance(data, dict):
            data = {}
        return data, None
    except requests.RequestException as e:
        return None, str(e)


def get_predictions(
    base_url: str,
    timeout: int = 60,
    ticker: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Tuple[Optional[List], Optional[str]]:
    """GET /predictions. Optional query params: ticker, model_name. Returns (list, None) or (None, error)."""
    try:
        params = {}
        if ticker:
            params["ticker"] = ticker
        if model_name:
            params["model_name"] = model_name
        r = requests.get(f"{base_url.rstrip('/')}/predictions", params=params or None, timeout=timeout)
        if not r.ok:
            return None, f"/predictions returned {r.status_code}"
        out = r.json()
        return out if isinstance(out, list) else [], None
    except requests.RequestException as e:
        return None, str(e)


def get_model_info(base_url: str, timeout: int = 60) -> Tuple[Optional[Dict], Optional[str]]:
    """GET /model_info. Returns (data, None) or (None, error_message). data is a dict when success."""
    try:
        r = requests.get(f"{base_url.rstrip('/')}/model_info", timeout=timeout)
        if not r.ok:
            return None, f"Backend returned {r.status_code}: {r.text[:200] if r.text else 'No body'}"
        data = r.json() if r.text else None
        if data is not None and not isinstance(data, dict):
            data = None
        return data, None
    except requests.RequestException as e:
        return None, str(e)


def get_feature_importance(base_url: str, timeout: int = 60) -> Tuple[Optional[Dict], Optional[str]]:
    """GET /feature_importance. Returns (data, None) or (None, error_message)."""
    if not (base_url or "").strip():
        return None, "Backend not configured"
    try:
        r = requests.get(f"{base_url.rstrip('/')}/feature_importance", timeout=timeout)
        if not r.ok:
            return None, None  # 404 treated as "not generated yet"
        return r.json(), None
    except requests.RequestException:
        return None, "Request failed"


def post_predict(
    base_url: str,
    ticker: str,
    as_of: str,
    horizon: int = 1,
    features: Optional[Dict[str, float]] = None,
    timeout: int = 60,
) -> Tuple[Optional[Dict], Optional[str]]:
    """POST /predict. Returns (response_dict, None) or (None, error_message)."""
    try:
        payload = {"ticker": ticker, "as_of": as_of, "horizon": horizon}
        if features is not None:
            payload["features"] = features
        r = requests.post(f"{base_url.rstrip('/')}/predict", json=payload, timeout=timeout)
        if not r.ok:
            try:
                err = r.json()
                detail = err.get("detail", r.text)
            except Exception:
                detail = r.text or f"Status {r.status_code}"
            return None, detail[:500] if isinstance(detail, str) else str(detail)[:500]
        return r.json(), None
    except requests.RequestException as e:
        return None, str(e)


def get_prices(
    base_url: str,
    ticker: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    timeout: int = 60,
) -> Tuple[Optional[List], Optional[str]]:
    """GET /prices. Returns (list of price rows, None) or (None, error_message)."""
    try:
        params = {"ticker": ticker}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        r = requests.get(f"{base_url.rstrip('/')}/prices", params=params, timeout=timeout)
        if not r.ok:
            return None, f"/prices returned {r.status_code}"
        out = r.json()
        return out if isinstance(out, list) else [], None
    except requests.RequestException as e:
        return None, str(e)
