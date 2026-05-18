from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from typing import Any

from dateutil import parser as date_parser

from chat_agent.db import NEWS_TABLE, ensure_schema, get_connection, get_env, log_action, utc_now_iso
from chat_agent.config import NEWS_FILTER_KEYWORDS, FOOD_SECURITY_KEYWORDS

FOOD_KEYWORDS = FOOD_SECURITY_KEYWORDS   # backward-compat alias

RSS_FEEDS = [
    "https://www.dawn.com/feeds/home",
    "https://tribune.com.pk/feed",
    "https://geo.tv/rss/top-stories",
    "https://www.thenews.com.pk/rss/1/1",
]

DIRECT_SCRAPE_URLS = [
    "https://www.dawn.com/business",
    "https://tribune.com.pk/business",
]


def _contains_food_keyword(text: str) -> bool:
    lowered = text.casefold()
    return any(keyword in lowered for keyword in FOOD_KEYWORDS)


def _normalize_date(value: Any) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Try RFC 2822 (RSS pubDate format)
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(text).date().isoformat()
    except Exception:
        pass
    # Try ISO format
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        pass
    # Try dateutil parser (handles "Sep 6, 2025", "6 September 2025" etc.)
    try:
        return date_parser.parse(text).date().isoformat()
    except Exception:
        pass
    # Last resort: first 10 chars if date-like
    if re.match(r'\d{4}-\d{2}', text[:7]):
        return text[:10]
    return None


def _extract_date_from_snippet(text: str | None) -> str | None:
    """Extract a date from a DuckDuckGo snippet like 'Sep 6, 2025 · The chair directed...'"""
    if not text:
        return None
    # Match leading date patterns in snippets
    patterns = [
        r'^(\w+ \d{1,2},? \d{4})\s*[·\-—]',  # "Sep 6, 2025 ·"
        r'(\d{4}-\d{2}-\d{2})',  # ISO embedded
        r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})',  # Month D, YYYY
        r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})',  # D Month YYYY
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return date_parser.parse(match.group(1)).date().isoformat()
            except Exception:
                continue
    return None


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _store_articles(articles: list[dict[str, Any]]) -> int:
    if not articles:
        return 0
    ensure_schema()
    with get_connection() as connection:
        cursor = connection.executemany(
            f"""
            INSERT OR IGNORE INTO {NEWS_TABLE}
                (title, content, date, source, url, keywords, created_at)
            VALUES
                (:title, :content, :date, :source, :url, :keywords, :created_at)
            """,
            articles,
        )
        return int(cursor.rowcount or 0)


def build_search_queries(region: str, commodities: list[str] | None = None) -> list[str]:
    base_commodities = commodities or ["wheat flour", "rice", "food prices", "shortage"]
    current_year = datetime.now().year
    queries: list[str] = []
    for commodity in base_commodities:
        queries.append(f"{commodity} price {region} Pakistan {current_year}")
        queries.append(f"{region} {commodity} shortage inflation Pakistan")
    queries.append(f"food security Pakistan {region} latest")
    queries.append(f"NDMA flood {region} Pakistan supply")
    return queries


def search_duckduckgo_langchain(query: str, num_results: int = 10) -> list[dict[str, Any]]:
    """Tier-1 web search using LangChain DuckDuckGo wrapper (no API key required)."""
    try:
        from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
    except Exception as exc:
        raise RuntimeError(
            "DuckDuckGo search requires langchain-community and duckduckgo-search packages"
        ) from exc

    max_results = max(1, min(num_results, int(get_env("DDG_MAX_RESULTS") or 10)))
    safesearch = get_env("DDG_SAFESEARCH") or "moderate"

    wrapper = DuckDuckGoSearchAPIWrapper(region="wt-wt", safesearch=safesearch, max_results=max_results)

    try:
        items = wrapper.results(query, max_results=max_results)
    except Exception as exc:
        raise RuntimeError(f"DuckDuckGo search failed: {exc}") from exc

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        snippet = str(item.get("snippet") or item.get("body") or "")
        if not _contains_food_keyword(f"{title} {snippet}"):
            continue
        link = str(item.get("link") or item.get("href") or "")
        # URL-based dedup to prevent duplicate articles across queries
        if link in seen_urls:
            continue
        seen_urls.add(link)
        # Truncate title to 200 chars
        if len(title) > 200:
            title = title[:197] + "..."
        # Extract date: try the date field first, then extract from snippet text
        raw_date = _normalize_date(item.get("date"))
        if not raw_date:
            raw_date = _extract_date_from_snippet(snippet)
        if not raw_date:
            raw_date = datetime.now(timezone.utc).date().isoformat()
        # Extract actual food-security keywords found in this article
        found_keywords = [kw for kw in FOOD_KEYWORDS if kw in f"{title} {snippet}".casefold()]
        results.append(
            {
                "title": title,
                "content": snippet,
                "url": link,
                "date": raw_date,
                "source": urllib.parse.urlparse(link).netloc,
                "keywords": ", ".join(found_keywords) if found_keywords else "food security",
                "created_at": utc_now_iso(),
            }
        )
    return results


def build_google_queries(region: str, commodities: list[str] | None = None) -> list[str]:
    """Compatibility shim. Prefer build_search_queries()."""
    return build_search_queries(region, commodities)


def search_google(query: str, num_results: int = 10) -> list[dict[str, Any]]:
    """Compatibility shim. Prefer search_duckduckgo_langchain()."""
    return search_duckduckgo_langchain(query, num_results)


def scrape_rss_feed(url: str, timeout: int = 10) -> list[dict[str, Any]]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; FoodSecurityBot/1.0)"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError(f"RSS fetch failed for {url}: {exc}") from exc

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise RuntimeError(f"RSS parse failed for {url}: {exc}") from exc

    items = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    results: list[dict[str, Any]] = []
    source_domain = urllib.parse.urlparse(url).netloc

    for item in items:
        title = (item.findtext("title") or "").strip()
        description = (item.findtext("description") or item.findtext("summary") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = item.findtext("pubDate") or item.findtext("published")
        description = _strip_html(description)
        if not _contains_food_keyword(f"{title} {description}"):
            continue
        results.append(
            {
                "title": title or description[:100],
                "content": description,
                "url": link,
                "date": _normalize_date(pub_date),
                "source": source_domain,
                "keywords": "rss",
                "created_at": utc_now_iso(),
            }
        )

    return results


def scrape_all_rss(feeds: list[str] | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for feed_url in feeds or RSS_FEEDS:
        try:
            results.extend(scrape_rss_feed(feed_url))
        except Exception:
            continue
    return results


def scrape_page_headlines(url: str, timeout: int = 12) -> list[dict[str, Any]]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; FoodSecurityBot/1.0)"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            html = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise RuntimeError(f"Direct scrape failed for {url}: {exc}") from exc

    headlines = re.findall(r"<(?:h[123]|a)[^>]*>([^<]{20,200})</(?:h[123]|a)>", html)
    source_domain = urllib.parse.urlparse(url).netloc
    results: list[dict[str, Any]] = []
    for headline in headlines:
        clean = re.sub(r"\s+", " ", _strip_html(headline)).strip()
        if _contains_food_keyword(clean):
            results.append(
                {
                    "title": clean,
                    "content": clean,
                    "url": url,
                    "date": datetime.now(timezone.utc).date().isoformat(),
                    "source": source_domain,
                    "keywords": "direct_scrape",
                    "created_at": utc_now_iso(),
                }
            )
    return results


def ingest_news_multisource(
    region: str = "National",
    *,
    run_id: str | None = None,
    use_web_search: bool = True,
    use_rss: bool = True,
    use_direct: bool = True,
    use_google: bool | None = None,
) -> dict[str, Any]:
    # Backward compatibility: if caller passes use_google explicitly, map to tier-1 web search toggle.
    if use_google is not None:
        use_web_search = use_google

    summary: dict[str, Any] = {
        "region": region,
        "duckduckgo": {"attempted": False, "fetched": 0, "inserted": 0, "error": None},
        "rss": {"attempted": False, "fetched": 0, "inserted": 0, "error": None},
        "direct": {"attempted": False, "fetched": 0, "inserted": 0, "error": None},
        "total_inserted": 0,
    }

    if use_web_search:
        summary["duckduckgo"]["attempted"] = True
        try:
            queries = build_search_queries(region)
            articles: list[dict[str, Any]] = []
            seen_urls: set[str] = set()
            for query in queries[:4]:
                for article in search_duckduckgo_langchain(query, num_results=5):
                    url = article.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        articles.append(article)
            inserted = _store_articles(articles)
            summary["duckduckgo"]["fetched"] = len(articles)
            summary["duckduckgo"]["inserted"] = inserted
        except Exception as exc:
            summary["duckduckgo"]["error"] = str(exc)

    if use_rss:
        summary["rss"]["attempted"] = True
        try:
            articles = scrape_all_rss()
            inserted = _store_articles(articles)
            summary["rss"]["fetched"] = len(articles)
            summary["rss"]["inserted"] = inserted
        except Exception as exc:
            summary["rss"]["error"] = str(exc)

    if use_direct:
        summary["direct"]["attempted"] = True
        try:
            articles: list[dict[str, Any]] = []
            for url in DIRECT_SCRAPE_URLS:
                try:
                    articles.extend(scrape_page_headlines(url))
                except Exception:
                    continue
            inserted = _store_articles(articles)
            summary["direct"]["fetched"] = len(articles)
            summary["direct"]["inserted"] = inserted
        except Exception as exc:
            summary["direct"]["error"] = str(exc)

    summary["total_inserted"] = (
        summary["duckduckgo"]["inserted"] + summary["rss"]["inserted"] + summary["direct"]["inserted"]
    )
    log_action(
        "multisource_news_ingestion",
        summary,
        run_id=run_id,
        trace_message=f"Multi-source ingestion completed: {summary['total_inserted']} articles inserted",
    )
    return summary


def scrape_kissan_wheat_prices() -> list[dict[str, Any]]:
    """Scrape live wheat prices from kissanstore.pk."""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        url = "https://kissanstore.pk/wheat-price-in-pakistan/"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        prices = []
        for table in soup.find_all("table"):
            for row in table.find_all("tr")[1:]:  # Skip header
                cols = [td.text.strip() for td in row.find_all(["th", "td"])]
                if len(cols) >= 3 and cols[0] and "Wheat" not in cols[0] and not cols[0].startswith("🌾"):
                    prices.append({
                        "city": cols[0],
                        "min_rate": cols[1],
                        "max_rate": cols[2]
                    })
        return prices
    except Exception as e:
        # If we fail, return an empty list so it doesn't break the pipeline
        return []
