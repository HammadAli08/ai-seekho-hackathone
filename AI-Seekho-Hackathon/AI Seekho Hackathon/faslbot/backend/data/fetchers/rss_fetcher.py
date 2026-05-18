import feedparser
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

FEEDS = [
    {"url": "https://www.dawn.com/feeds/business", "source": "Dawn"},
    {"url": "https://arynews.tv/feed/",            "source": "ARY News"},
    {"url": "https://www.geo.tv/rss/latest-news",  "source": "Geo News"},
]

AGRI_KEYWORDS = [
    "wheat", "rice", "sugar", "tomato", "onion", "potato", "flour", "atta",
    "flood", "drought", "crop", "mandi", "kisan", "farmer", "food price",
    "supply", "harvest", "production", "import", "export", "agriculture",
    "گندم", "چاول", "چینی", "کسان", "سیلاب", "فصل", "منڈی", "آلو", "پیاز"
]


async def fetch_news() -> List[Dict]:
    tasks = [_fetch_single_feed(feed) for feed in FEEDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    articles = []
    for result in results:
        if isinstance(result, list):
            articles.extend(result)
        else:
            logger.warning(f"Feed fetch failed: {result}")

    articles.sort(key=lambda x: x.get("published", ""), reverse=True)
    logger.info(f"Fetched {len(articles)} relevant news articles")
    return articles


async def _fetch_single_feed(feed_config: Dict) -> List[Dict]:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(feed_config["url"])
            parsed = feedparser.parse(resp.text)

        cutoff = datetime.now() - timedelta(hours=48)
        articles = []

        for entry in parsed.entries:
            title = entry.get("title", "")
            summary = entry.get("summary", entry.get("description", ""))[:500]

            text_lower = (title + " " + summary).lower()
            matched_keywords = [kw for kw in AGRI_KEYWORDS if kw.lower() in text_lower]

            if matched_keywords:
                articles.append({
                    "title": title,
                    "summary": summary,
                    "published": entry.get("published", datetime.now().isoformat()),
                    "url": entry.get("link", ""),
                    "source": feed_config["source"],
                    "relevance_keywords": matched_keywords
                })

        return articles
    except Exception as e:
        logger.error(f"Failed to fetch {feed_config['source']}: {e}")
        return []