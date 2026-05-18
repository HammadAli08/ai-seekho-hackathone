from services.gemini_service import call_gemini
from data.processors.price_processor import compare_prices
from services.firebase_service import update_pipeline_status
from utils.json_utils import parse_llm_json
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

INSIGHT_PROMPT = """
You are FaslBot's Insight Extraction Agent for Pakistan's agricultural commodity markets.
You analyze real price data and news to find SPECIFIC, NON-TRIVIAL insights that matter
to Pakistani farmers, traders, and procurement managers.
CURRENT PRICE DATA:
{price_comparison}
RECENT AGRICULTURAL NEWS:
{news_headlines}
YOUR TASK:
Find the SINGLE most important, actionable insight from this data.
Look for: price arbitrage between cities, sudden price spikes/drops, news-corroborated
supply disruptions, seasonal opportunities, or import/export policy impacts.
Return ONLY valid JSON matching this exact schema:
{schema}
"""
INSIGHT_SCHEMA = """{
  "type": "price_arbitrage|price_spike|supply_disruption|price_opportunity|seasonal_pattern",
  "headline": "string (max 25 words, plain English)",
  "headline_urdu": "string (Urdu translation of headline)",
  "commodity": "string",
  "cities_affected": ["string"],
  "key_metric": "string (the most important number/stat)",
  "supporting_data": {
    "price_comparisons": {},
    "percentage_change": 0.0,
    "news_connection": "string or null"
  },
  "confidence": "high|medium|low",
  "time_horizon": "string",
  "urgency": "high|medium|low"
}"""


async def insight_extractor_agent(state: dict) -> dict:
    logger.info("[Agent 2] InsightExtractorAgent starting...")
    trace_entry = {
        "agent": "InsightExtractorAgent",
        "step": 2,
        "started_at": datetime.now().isoformat(),
        "inputs": {"price_records": len(state.get("raw_prices", []))}
    }

    try:
        processed = compare_prices(state["raw_prices"])
        price_text = _format_price_comparison(processed, state["raw_prices"])
        news_text = _format_news_headlines(state.get("raw_news", [])[:10])

        prompt = INSIGHT_PROMPT.format(
            price_comparison=price_text,
            news_headlines=news_text,
            schema=INSIGHT_SCHEMA
        )

        response = await call_gemini(prompt, temperature=0.3)

        insight = parse_llm_json(response)
        if insight is None:
            raise ValueError("Failed to parse insight JSON from LLM response")

        trace_entry["output"] = insight
        trace_entry["reasoning"] = f"Analyzed {len(state['raw_prices'])} price records. Found: {insight.get('type')}"
        trace_entry["completed_at"] = datetime.now().isoformat()

        await update_pipeline_status(state["run_id"], "running",
                                      {"current_agent": "insight_extractor", "insight_found": insight.get("headline")})

        return {
            "processed_prices": processed,
            "insight": insight,
            "agent_trace": [trace_entry]
        }

    except Exception as e:
        logger.error(f"[Agent 2] InsightExtractor failed: {e}")
        trace_entry["error"] = str(e)
        return {"insight": None, "agent_trace": [trace_entry]}


def _format_price_comparison(processed: dict, raw_records: list = None) -> str:
    lines = []
    # Extract unit info from raw records if available
    unit_by_commodity = {}
    if raw_records:
        for record in raw_records:
            commodity = record.get("commodity", "Unknown")
            if commodity not in unit_by_commodity:
                unit_by_commodity[commodity] = record.get("unit", "kg")

    for commodity, city_prices in processed.get("by_commodity", {}).items():
        if len(city_prices) >= 2:
            unit = unit_by_commodity.get(commodity, "kg")
            prices = [(city, p) for city, p in city_prices.items()]
            prices.sort(key=lambda x: x[1])
            min_p, max_p = prices[0], prices[-1]
            diff_pct = ((max_p[1] - min_p[1]) / min_p[1]) * 100
            lines.append(f"{commodity}: Low={min_p[0]} PKR{min_p[1]:.0f}/{unit}, High={max_p[0]} PKR{max_p[1]:.0f}/{unit} (diff: {diff_pct:.1f}%)")
    return "\n".join(lines)


def _format_news_headlines(news: list) -> str:
    if not news:
        return "No recent agricultural news available."
    lines = [f"- [{n.get('source', '')}] {n.get('title', '')}" for n in news]
    return "\n".join(lines)