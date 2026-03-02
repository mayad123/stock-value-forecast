"""
News ingestion: Marketaux API -> raw JSON per ticker + normalized table + manifest.
Raw responses are never overwritten; each run uses a unique ingestion timestamp.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.ingest.marketaux import (  # noqa: E402
    fetch_news,
    get_api_key,
    throttle_wait,
)


def _datetime_to_version(ts: datetime) -> str:
    """Stable version string for manifests and paths (filesystem-safe)."""
    return ts.strftime("%Y-%m-%dT%H-%M-%S")


def _normalize_article(article: Dict[str, Any], ticker: str) -> List[Dict[str, Any]]:
    """
    Extract one row per (article, entity) for the given ticker.
    Returns list of dicts: ticker, publication_timestamp, headline, source, sentiment_score, match_score, uuid, url.
    """
    rows = []
    published_at = article.get("published_at") or ""
    title = (article.get("title") or "").strip()
    source = (article.get("source") or "").strip()
    uuid = article.get("uuid") or ""
    url = article.get("url") or ""
    relevance_score = article.get("relevance_score")
    entities = article.get("entities") or []
    for ent in entities:
        if (ent.get("symbol") or "").strip().upper() != ticker.upper():
            continue
        sentiment = ent.get("sentiment_score")
        if sentiment is None:
            sentiment = ""
        try:
            sentiment_float = float(sentiment) if sentiment != "" else None
        except (TypeError, ValueError):
            sentiment_float = None
        match_score = ent.get("match_score")
        if match_score is not None:
            try:
                match_score = float(match_score)
            except (TypeError, ValueError):
                match_score = None
        rows.append({
            "ticker": ticker,
            "publication_timestamp": published_at,
            "headline": title,
            "source": source,
            "sentiment_score": sentiment_float,
            "match_score": match_score,
            "relevance_score": relevance_score if relevance_score is not None else None,
            "article_uuid": uuid,
            "url": url,
        })
    if not rows and title:
        rows.append({
            "ticker": ticker,
            "publication_timestamp": published_at,
            "headline": title,
            "source": source,
            "sentiment_score": None,
            "match_score": None,
            "relevance_score": relevance_score if relevance_score is not None else None,
            "article_uuid": uuid,
            "url": url,
        })
    return rows


def run_ingest_news(
    config: Dict[str, Any],
    data_raw_root: Optional[Path] = None,
    log: Optional[Any] = None,
) -> str:
    """
    Ingest financial news for configured tickers via Marketaux.
    - Saves raw API responses under data/raw/news/{ticker}/{ingestion_timestamp}.json
    - Saves normalized table under data/raw/news_normalized/{dataset_version}/
    - Saves manifest under data/raw/manifests/news_{dataset_version}.json
    Returns dataset_version (ingestion timestamp string).
    """
    if config.get("mode") == "recruiter_demo":
        print("Demo mode uses sample data. Use live_apis mode for ingestion.", file=sys.stderr)
        sys.exit(1)

    if log is None:
        def log(msg: str) -> None:
            print(f"[INGEST] {msg}")

    paths_cfg = config.get("paths", {})
    raw_root = data_raw_root or Path(paths_cfg.get("data_raw", "data/raw"))
    if not raw_root.is_absolute():
        raw_root = _REPO_ROOT / raw_root

    tickers = config.get("tickers", {}).get("symbols", [])
    if not tickers:
        raise ValueError("Config has no tickers.symbols")

    api_key = get_api_key()
    ingestion_time = datetime.utcnow()
    dataset_version = _datetime_to_version(ingestion_time)

    news_cfg = config.get("news_ingest", {})
    date_start = news_cfg.get("published_after") or config.get("time_horizon", {}).get("ingest_start")
    date_end = news_cfg.get("published_before") or config.get("time_horizon", {}).get("train_end") or config.get("time_horizon", {}).get("test_start")
    limit = int(news_cfg.get("limit", 50))
    language = news_cfg.get("language", "en")

    raw_news_dir = raw_root / "news"
    normalized_dir = raw_root / "news_normalized" / dataset_version
    manifests_dir = raw_root / "manifests"
    raw_news_dir.mkdir(parents=True, exist_ok=True)
    manifests_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir.mkdir(parents=True, exist_ok=True)

    log(f"News dataset version: {dataset_version}")
    log(f"Tickers: {len(tickers)}, published_after={date_start}, published_before={date_end}, limit={limit}")

    api_endpoint = "https://api.marketaux.com/v1/news/all"
    raw_paths: List[str] = []
    all_rows: List[Dict[str, Any]] = []
    max_pages = int(news_cfg.get("max_pages", 20))

    for i, symbol in enumerate(tickers):
        ticker_dir = raw_news_dir / symbol
        ticker_dir.mkdir(parents=True, exist_ok=True)
        raw_path = ticker_dir / f"{dataset_version}.json"
        if raw_path.exists():
            log(f"Raw file already exists (skip fetch): {raw_path}")
            with open(raw_path) as f:
                raw = json.load(f)
        else:
            log(f"Fetching news {symbol} ({i + 1}/{len(tickers)})")
            pages_data: List[Dict[str, Any]] = []
            page = 1
            while page <= max_pages:
                throttle_wait()
                data = fetch_news(
                    api_key,
                    symbols=[symbol],
                    published_after=date_start,
                    published_before=date_end,
                    limit=limit,
                    page=page,
                    language=language,
                    filter_entities=True,
                )
                pages_data.append(data)
                meta = data.get("meta") or {}
                returned = meta.get("returned", 0)
                if returned < limit:
                    break
                page += 1
            raw = {"meta": {"pages_fetched": len(pages_data)}, "pages": pages_data}
            with open(raw_path, "w") as f:
                json.dump(raw, f, indent=2)

        raw_paths.append(str(raw_path.relative_to(raw_root)))
        for page_blob in raw.get("pages", [raw]):
            if isinstance(page_blob, dict) and "data" not in page_blob:
                continue
            data_list = page_blob.get("data", []) if isinstance(page_blob, dict) else []
            for art in data_list:
                all_rows.extend(_normalize_article(art, symbol))

    all_rows.sort(key=lambda r: (r["ticker"], r["publication_timestamp"] or ""))

    if all_rows:
        _write_normalized_csv(all_rows, normalized_dir / "news.csv")
    normalized_paths = [str((normalized_dir / "news.csv").relative_to(raw_root))] if all_rows else []

    pub_dates = [r["publication_timestamp"][:10] for r in all_rows if r.get("publication_timestamp")]
    date_range = {"min": min(pub_dates), "max": max(pub_dates)} if pub_dates else {}

    manifest = {
        "dataset_version": dataset_version,
        "ingestion_timestamp": ingestion_time.isoformat() + "Z",
        "api_endpoint": api_endpoint,
        "tickers": tickers,
        "date_range": date_range,
        "published_after": date_start,
        "published_before": date_end,
        "raw_paths": raw_paths,
        "normalized_paths": normalized_paths,
    }
    manifest_path = manifests_dir / f"news_{dataset_version}.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    log(f"News manifest: {manifest_path}")
    log(f"Normalized: {normalized_dir}, rows={len(all_rows)}")
    return dataset_version


def _write_normalized_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    keys = [
        "ticker", "publication_timestamp", "headline", "source",
        "sentiment_score", "match_score", "relevance_score", "article_uuid", "url",
    ]
    with open(path, "w") as f:
        f.write(",".join(keys) + "\n")
        for r in rows:
            line = ",".join(_csv_cell(r.get(k)) for k in keys)
            f.write(line + "\n")


def _csv_cell(val: Any) -> str:
    if val is None:
        return ""
    s = str(val)
    if "," in s or '"' in s or "\n" in s:
        return '"' + s.replace('"', '""') + '"'
    return s
