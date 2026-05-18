from data.fetchers.pbs_fetcher import fetch_prices
from data.fetchers.rss_fetcher import fetch_news
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def data_ingestor_agent(state: dict) -> dict:
    logger.info("[Agent 1] DataIngestorAgent starting...")
    trace_entry = {"agent": "DataIngestorAgent", "step": 1, "started_at": datetime.now().isoformat()}

    try:
        prices = await fetch_prices()
        news = await fetch_news()

        trace_entry["output"] = f"Fetched {len(prices)} prices and {len(news)} news articles"
        trace_entry["completed_at"] = datetime.now().isoformat()

        return {"raw_prices": prices, "raw_news": news, "agent_trace": [trace_entry]}

    except Exception as e:
        logger.error(f"[Agent 1] Ingestor failed: {e}")
        trace_entry["error"] = str(e)
        return {"raw_prices": [], "raw_news": [], "agent_trace": [trace_entry]}