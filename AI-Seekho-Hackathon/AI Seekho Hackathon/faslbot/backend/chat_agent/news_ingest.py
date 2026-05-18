from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from chat_agent.db import NEWS_TABLE, ensure_schema, get_connection, get_env, json_dumps, log_action, normalize_region, utc_now_iso
from chat_agent.config import NEWS_FILTER_KEYWORDS

PAKISTANI_NEWS_SOURCES = [
    "https://www.dawn.com",
    "https://tribune.com.pk",
    "https://geo.tv",
    "https://thenews.com.pk",
]

DOMAIN_TO_REGION = {
    "dawn.com": "Pakistan",
    "dawn.pk": "Pakistan",
    "tribune.com.pk": "Pakistan",
    "geo.tv": "Pakistan",
    "geo.com.pk": "Pakistan",
    "thenews.com.pk": "Pakistan",
    "theexpressnews.com": "Pakistan",
    "ary.com.pk": "Pakistan",
    "24newshd.tv": "Pakistan",
}

CITY_TO_REGION = {
    "karachi": "Sindh",
    "lahore": "Punjab",
    "islamabad": "Islamabad Capital Territory",
    "rawalpindi": "Punjab",
    "peshawar": "Khyber Pakhtunkhwa",
    "quetta": "Balochistan",
    "faisalabad": "Punjab",
    "multan": "Punjab",
    "hyderabad": "Sindh",
    "sialkot": "Punjab",
    "gilgit": "Gilgit-Baltistan",
    "skardu": "Gilgit-Baltistan",
    "mirpur": "Azad Jammu and Kashmir",
    "muzaffarabad": "Azad Jammu and Kashmir",
}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _first_present(item: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        current: Any = item
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if current not in (None, ""):
            return current
    return None


def _extract_date_from_text(text: str | None) -> str | None:
    """Extract a date from free text using regex patterns."""
    if not text:
        return None
    # Match patterns like: "Sep 6, 2025", "September 6, 2025", "6 Sep 2025",
    # "2025-09-06", "May 15, 2026", "15 May 2026"
    patterns = [
        r'(\d{4}-\d{2}-\d{2})',  # ISO: 2025-09-06
        r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})',  # Sep 6, 2025
        r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})',  # 6 Sep 2025
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                from dateutil import parser as date_parser
                return date_parser.parse(match.group(1)).date().isoformat()
            except Exception:
                continue
    return None


def _normalize_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        return datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()

    text = str(value).strip()
    if not text:
        return None
    # Try ISO format first
    try:
        normalized = text.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError:
        pass
    # Try dateutil parser (handles "Sep 6, 2025" etc.)
    try:
        from dateutil import parser as date_parser
        return date_parser.parse(text).date().isoformat()
    except Exception:
        pass
    # Try regex extraction from embedded text
    extracted = _extract_date_from_text(text)
    if extracted:
        return extracted
    # Last resort: return first 10 chars if they look date-like
    if re.match(r'\d{4}-\d{2}', text[:7]):
        return text[:10]
    return None


def _normalize_source(value: Any) -> str | None:
    if isinstance(value, dict):
        return _clean_text(value.get("name") or value.get("title") or value.get("domain") or value.get("url"))
    return _clean_text(value)


def _extract_domain(url: str | None) -> str | None:
    """Extract domain from URL."""
    if not url:
        return None
    try:
        import urllib.parse as up
        parsed = up.urlparse(url)
        return parsed.netloc or parsed.path
    except Exception:
        return None


def _infer_region_from_source(source: str | None) -> str:
    """Infer region from source domain."""
    if not source:
        return "Pakistan"
    source_lower = source.casefold()
    for domain, region in DOMAIN_TO_REGION.items():
        if domain in source_lower:
            return region
    return "Pakistan"


def _infer_region_from_text(title: str | None, description: str | None) -> str:
    """Infer region from city mentions in title or description."""
    text = " ".join(filter(None, [title, description])).casefold()
    for city, region in CITY_TO_REGION.items():
        if city in text:
            return region
    return "Pakistan"


def _normalize_item(item: dict[str, Any], source_url: str = "") -> dict[str, Any] | None:
    """Normalize a news item from Headline News Scraper."""
    title = _clean_text(
        _first_present(item, ["title", "headline", "name"])
    )
    description = _clean_text(
        _first_present(item, ["description", "summary", "content", "text"])
    )
    if not title and not description:
        return None

    # Truncate title to prevent concatenation issues
    if title and len(title) > 200:
        title = title[:197] + "..."

    source = _normalize_source(
        _first_present(item, ["source", "publisher"])
    )
    url = _clean_text(_first_present(item, ["url", "link"]))
    date_value = _first_present(
        item,
        ["publishedAt", "published", "scrapedAt", "createdAt", "date"],
    )
    
    # Try to parse date; if still null, attempt extraction from title/content
    parsed_date = _normalize_date(date_value)
    if not parsed_date:
        parsed_date = _extract_date_from_text(title) or _extract_date_from_text(description)
    # If still no date, use today as a last resort for fresh scrapes
    if not parsed_date:
        parsed_date = datetime.now(timezone.utc).date().isoformat()
    
    inferred_source = source or _extract_domain(url) or _extract_domain(source_url) or "Apify"
    inferred_region = _infer_region_from_text(title, description)
    
    return {
        "title": title or description[:120],
        "content": description,
        "date": parsed_date,
        "source": inferred_source,
        "url": url,
        "keywords": inferred_region or "Pakistan",
        "created_at": utc_now_iso(),
    }


ALLOWED_KEYWORDS = NEWS_FILTER_KEYWORDS   # backward-compat alias


def _contains_allowed_keywords(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.casefold()
    for kw in ALLOWED_KEYWORDS:
        if kw in lowered:
            return True
    return False


def _apify_actor_url(actor_id: str, token: str) -> str:
    actor_path = actor_id.replace("/", "~")
    params = urllib.parse.urlencode({"token": token, "format": "json", "clean": "true"})
    return f"https://api.apify.com/v2/acts/{actor_path}/run-sync-get-dataset-items?{params}"


def _default_actor_input(urls: list[str], max_items: int) -> dict[str, Any]:
    """Build input for misceres/news-scraper actor."""
    return {
        "startUrls": [{"url": u} for u in urls],
        "maxArticlesPerCrawl": max_items,
        "onlyNewArticles": False,
    }


def _coerce_url_list(value: Any) -> list[str]:
    """Coerce value to URL list."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _resolve_actor_input(urls: list[str]) -> dict[str, Any]:
    """Resolve Apify actor input, allowing override via env var."""
    configured = get_env("APIFY_INPUT_JSON")
    if not configured:
        return _default_actor_input(urls, max_items=50)

    try:
        payload = json.loads(configured)
    except json.JSONDecodeError as exc:
        raise ValueError("APIFY_INPUT_JSON must contain valid JSON") from exc

    if isinstance(payload, dict):
        if "startUrls" in payload:
            payload["startUrls"] = [{"url": str(item.get("url", ""))} for item in payload.get("startUrls", []) if isinstance(item, dict) and str(item.get("url", "")).strip()]
        else:
            payload["startUrls"] = [{"url": u} for u in _coerce_url_list(payload.get("urls", urls))]
        payload.pop("urls", None)
        return payload
    raise ValueError("APIFY_INPUT_JSON must be a JSON object")


def call_apify_news_actor(
    *,
    urls: list[str] | None = None,
    actor_id: str | None = None,
) -> list[tuple[dict[str, Any], str]]:
    """Call Apify Headline News Scraper and return (item, source_url) tuples."""
    token = get_env("APIFY_TOKEN", "APIFY_API_KEY")
    if not token:
        raise RuntimeError("APIFY_TOKEN is missing")

    resolved_urls = urls or PAKISTANI_NEWS_SOURCES
    resolved_actor_id = actor_id or get_env("APIFY_ACTOR_ID") or "misceres/news-scraper"
    payload = _resolve_actor_input(resolved_urls)
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        _apify_actor_url(resolved_actor_id, token),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Apify actor failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Apify actor request failed: {exc.reason}") from exc

    if not isinstance(data, list):
        raise RuntimeError("Apify response did not contain dataset items")
    # Filter items aggressively by allowed keywords to avoid irrelevant scraping
    results: list[tuple[dict[str, Any], str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = _clean_text(_first_present(item, ["title", "headline", "name"]))
        description = _clean_text(_first_present(item, ["description", "summary", "content", "text"]))
        combined = " ".join(filter(None, [title, description]))
        if _contains_allowed_keywords(combined):
            results.append((item, ""))
    return results


def store_news_items(items: list[tuple[dict[str, Any], str]]) -> int:
    """Store news items with region inference."""
    ensure_schema()
    normalized_items = [
        normalized
        for item_data, source_url in items
        if (normalized := _normalize_item(item_data, source_url)) is not None
    ]
    if not normalized_items:
        return 0

    with get_connection() as connection:
        cursor = connection.executemany(
            f"""
            INSERT OR IGNORE INTO {NEWS_TABLE}
                (title, content, date, source, url, keywords, created_at)
            VALUES
                (:title, :content, :date, :source, :url, :keywords, :created_at)
            """,
            normalized_items,
        )
        return int(cursor.rowcount if cursor.rowcount is not None else 0)


def ingest_news(
    *,
    urls: list[str] | None = None,
    actor_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Ingest news from Pakistani outlets using Headline News Scraper."""
    resolved_urls = urls or PAKISTANI_NEWS_SOURCES
    items = call_apify_news_actor(urls=resolved_urls, actor_id=actor_id)
    # additional safeguard: discard items that do not clearly contain allowed keywords
    filtered = []
    discarded_count = 0
    for item_data, src in items:
        title = _clean_text(_first_present(item_data, ["title", "headline", "name"]))
        description = _clean_text(_first_present(item_data, ["description", "summary", "content", "text"]))
        if _contains_allowed_keywords(" ".join(filter(None, [title, description]))):
            filtered.append((item_data, src))
        else:
            discarded_count += 1

    inserted = store_news_items(filtered)
    result = {
        "source": "apify_headline_news_scraper",
        "actor_id": actor_id or get_env("APIFY_ACTOR_ID") or "misceres/news-scraper",
        "fetched": len(items) + 0,
        "inserted": inserted,
        "discarded": discarded_count,
        "urls": resolved_urls,
    }
    log_action("news_ingestion", result, run_id=run_id, trace_message="Apify Headline News Scraper ingestion completed")
    return result


if __name__ == "__main__":
    print(json_dumps(ingest_news()))
