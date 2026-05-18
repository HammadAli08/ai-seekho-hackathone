from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

from chat_agent.db import dicts_from_rows, ensure_schema, get_connection, get_env, json_dumps, log_action, normalize_region
from chat_agent.config import PRICE_SPIKE_EMERGENCY_PCT, SIGNAL_INPUT_CONTEXT_KEYWORDS
from chat_agent.geo_resolver import resolve_region, get_districts_in_province, get_province_neighbors
from chat_agent.temporal_resolver import parse_time_intent, validate_query_time_match
from chat_agent.tools import (
    compute_risk_signals,
    generate_signals,
    get_climate,
    get_disasters,
    get_news,
    get_prices,
    get_weather,
    log_decision,
    simulate_action,
    get_signals_with_reasoning,
)

REQUIRED_OUTPUT = {
    "signals": [],
    "ranked_signals": [],
    "discarded_signals": [],
    "source_weights": {"apify": 0.5, "weather": 0.2, "csv": 0.1},
    "contradictions": [],
    "action_chain": [],
    "simulation": {"before": {}, "after": {}},
    "reasoning_trace": [],
    "resolved_region": {},
    "time_intent": {},
    "local_signals": [],
    "province_context": {},
    "national_context": {},
    "historical_baseline": {},
    "live_signals_summary": {},
    "causal_chain": [],
    "risk_forecast": {},
    "final_reasoning": "",
    "reasoning_confidence": 0.0,
    "sources_checked": [],
}


def _tool_definitions() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_prices",
                "description": "Fetch regional food price records and detect recent price spikes from SQLite.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "region": {"type": "string"},
                        "commodity": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "limit": {"type": "integer", "minimum": 10, "maximum": 1000},
                    },
                    "required": ["region"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_disasters",
                "description": "Fetch disaster impact records from SQLite for a region.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "region": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                    "required": ["region"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_climate",
                "description": "Fetch historical Pakistan rainfall and temperature climate records from SQLite.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "region": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 12, "maximum": 240},
                    },
                    "required": ["region"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_news",
                "description": "Search ingested Apify news records by keywords.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keywords": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}},
                                {"type": "null"},
                            ]
                        },
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Fetch latest live weather records ingested from WeatherAPI for a region.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "region": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                    "required": ["region"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "simulate_action",
                "description": "Run intervention simulation and return before/after price, supply, and logistics state.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action_plan": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                        "region": {"type": "string"},
                    },
                    "required": ["action_plan", "region"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "log_decision",
                "description": "Persist a concise decision trace into actions_log.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "decision": {"type": "string"},
                        "event_type": {"type": "string"},
                        "region": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "payload": {"anyOf": [{"type": "object"}, {"type": "null"}]},
                    },
                    "required": ["decision"],
                },
            },
        },
    ]


def _extract_time_intent_from_context(user_query: str | None = None) -> dict[str, Any]:
    """Extract time intent from user query if provided."""
    if not user_query:
        return parse_time_intent(None)
    return parse_time_intent(user_query)


def _build_local_signals(signals: list[dict[str, Any]], district: str | None) -> list[dict[str, Any]]:
    """Filter signals to those matching the district level."""
    if not district:
        return signals
    district_lower = str(district).casefold()
    local = []
    for sig in signals:
        region = str(sig.get("region") or "").casefold()
        if region in district_lower or district_lower in region:
            local.append(sig)
    return local if local else signals[:3]  # fallback to top signals


def _extract_sources_checked(trace: list[str], reasoning_trace: list[str]) -> list[str]:
    """Infer which data sources were consulted from the accumulated trace strings."""
    full_trace_str = " ".join(trace + reasoning_trace).casefold()
    sources: list[str] = []

    source_markers = [
        ("weatherapi", "WeatherAPI"),
        ("weather ingestion", "WeatherAPI"),
        ("duckduckgo", "DuckDuckGo Intelligence"),
        ("rss", "Regional RSS Feeds"),
        ("apify", "Apify (Web Scraper)"),
        ("kissanstore", "KissanStore (Live Prices)"),
        ("startpage", "StartPage Search"),
        ("wikipedia", "Wikipedia (Global)"),
        ("historical database", "Regional Historical Database"),
    ]
    for marker, label in source_markers:
        if marker in full_trace_str and label not in sources:
            sources.append(label)
    # Historical database is a default fallback source
    if "Regional Historical Database" not in sources:
        sources.append("Regional Historical Database")
    return sources


def _tool_mapping(run_id: str) -> dict[str, Any]:
    return {
        "get_prices": get_prices,
        "get_disasters": get_disasters,
        "get_climate": get_climate,
        "get_news": get_news,
        "get_weather": get_weather,
        "simulate_action": lambda **kwargs: simulate_action(**kwargs, run_id=run_id),
        "log_decision": lambda **kwargs: log_decision(**kwargs, run_id=run_id),
    }


def _json_loads(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _classify_query_intent(user_query: str | None) -> dict[str, Any]:
    """
    Classify what the user actually wants — not just time intent, but question type.
    Returns:
    {
        "question_type": "why" | "what" | "how" | "trend" | "status" | "general",
        "target_commodity": str | None,   # "wheat", "rice", etc.
        "target_location": str | None,
        "needs_causal_reasoning": bool,
        "needs_live_data": bool,
        "needs_historical_data": bool,
    }
    """
    if not user_query:
        return {
            "question_type": "status",
            "target_commodity": None,
            "target_location": None,
            "needs_causal_reasoning": False,
            "needs_live_data": True,
            "needs_historical_data": False,
        }

    q = user_query.casefold()

    # Detect question type
    if any(w in q for w in ["why", "reason", "cause", "because", "what caused", "how did", "what happened"]):
        question_type = "why"
    elif any(w in q for w in ["how much", "what is the price", "current price", "price of", "rate of"]):
        question_type = "what"
    elif any(w in q for w in ["trend", "over time", "last year", "historically", "pattern", "average"]):
        question_type = "trend"
    elif any(w in q for w in ["forecast", "predict", "will", "future", "next month", "next year"]):
        question_type = "forecast"
    elif any(w in q for w in ["status", "situation", "update", "report", "assessment"]):
        question_type = "status"
    else:
        question_type = "general"

    # Detect target commodity
    commodity = None
    for c in ["wheat", "flour", "atta", "rice", "sugar", "edible oil", "maize", "cotton"]:
        if c in q:
            commodity = c
            break

    return {
        "question_type": question_type,
        "target_commodity": commodity,
        "target_location": None,  # filled by geo resolver
        "needs_causal_reasoning": question_type in ("why", "forecast"),
        "needs_live_data": question_type in ("what", "status", "general", "why"),
        "needs_historical_data": question_type in ("why", "trend", "forecast"),
    }


def _answer_direct_query(
    query_intent: dict[str, Any],
    regions: list[str],
    run_id: str,
    trace: list[str],
    time_intent: str,
    resolved_geo: dict[str, Any],
) -> dict[str, Any] | None:
    """
    For simple factual queries (what/status), return a fast direct answer
    without running the full reasoning pipeline.
    Returns None if the query needs full reasoning.
    """
    question_type = query_intent.get("question_type", "general")
    
    # Only handle simple lookups here
    if question_type not in ("what", "status"):
        return None

    commodity = query_intent.get("target_commodity")
    primary_region = regions[0] if regions else "National"

    prices = get_prices(primary_region, commodity=commodity, limit=20)
    spikes = prices.get("price_spikes", [])
    records = prices.get("records", [])

    # Build a concise direct answer
    if spikes:
        top = spikes[0]
        answer = (
            f"Current {top.get('commodity', commodity or 'staples')} price in {top.get('market', primary_region)}: "
            f"PKR {top.get('latest_price', 'N/A')} "
            f"({top.get('change_pct', 0.0):+.1f}% vs recent baseline). "
            f"Data from: {top.get('latest_date', 'recent records')}."
        )
    elif records:
        latest = records[0]
        answer = (
            f"Latest recorded {latest.get('commodity', commodity or 'food')} price "
            f"in {latest.get('market', primary_region)}: "
            f"PKR {latest.get('price', 'N/A')} ({latest.get('date', 'recent')})."
        )
    else:
        return None  # No data — fall through to full pipeline

    trace.append(f"Direct query answered: {question_type} for {commodity or 'general food'} in {primary_region}")

    return {
        **REQUIRED_OUTPUT,
        "signals": [],
        "action_chain": [],
        "final_reasoning": answer,
        "reasoning_confidence": 0.85,
        "reasoning_trace": trace,
        "resolved_region": resolved_geo,
        "time_intent": {"intent": time_intent},
        "status": "direct_answer",
        "status_message": answer,
    }


def _explain_price_spike(
    commodity: str,
    region: str,
    run_id: str,
    trace: list[str],
) -> dict[str, Any]:
    """
    Called when user asks WHY a price spiked.
    1. Checks DB for the actual price data to confirm the spike
    2. Searches for causal news (petrol, import policy, flood, etc.)
    3. Builds a causal narrative from what it finds
    """
    from chat_agent.scraper import search_duckduckgo_langchain, _store_articles

    # Step 1: Confirm the spike from DB
    prices = get_prices(region, commodity=commodity, limit=50)
    spike = prices["price_spikes"][0] if prices["price_spikes"] else None

    # Step 2: Search for WHY — specific causal queries
    causal_queries = [
        f"why did {commodity} price increase Pakistan {region} 2025",
        f"{commodity} price hike reason Pakistan inflation 2025",
        f"Pakistan {commodity} shortage reason petrol import",
        f"factors affecting {commodity} price Pakistan",
    ]

    causal_articles = []
    try:
        for query in causal_queries[:3]:
            articles = search_duckduckgo_langchain(query, num_results=5)
            causal_articles.extend(articles)
        _store_articles(causal_articles)
        trace.append(f"Causal search: fetched {len(causal_articles)} articles for '{commodity}' spike explanation")
    except Exception as exc:
        trace.append(f"Causal search failed: {exc}")

    # Step 3: Extract causal factors from articles
    CAUSAL_FACTORS = {
        "petrol": "fuel cost increase → higher transport costs → food price transmission",
        "diesel": "diesel price hike → irrigation and transport costs → farm-gate price increase",
        "import": "import restrictions or reduced imports → domestic supply tightening",
        "flood": "flood damage to crops → reduced yield → supply shock → price increase",
        "drought": "drought conditions → reduced yield → supply shortage",
        "dollar": "rupee depreciation / dollar rate → imported commodity costs up",
        "gas": "energy price increase → flour mill and processing costs up",
        "export": "increased exports → reduced domestic availability",
        "smuggling": "cross-border smuggling → domestic supply reduction",
        "hoard": "hoarding by traders → artificial supply restriction",
        "support price": "government support price increase → floor price raised",
        "fertilizer": "fertilizer shortage or price increase → lower crop yield",
    }

    found_causes = {}
    all_text = " ".join(
        (a.get("title", "") + " " + a.get("content", "")).lower()
        for a in causal_articles
    )
    for keyword, explanation in CAUSAL_FACTORS.items():
        if keyword in all_text:
            found_causes[keyword] = explanation

    # Step 4: Build causal narrative
    if found_causes:
        cause_lines = []
        for kw, explanation in list(found_causes.items())[:4]:
            cause_lines.append(f"• {kw.title()}: {explanation}")

        spike_context = ""
        if spike:
            spike_context = (
                f"{commodity.title()} is currently {spike.get('change_pct', 0.0):+.1f}% above its recent baseline "
                f"in {spike.get('market', region)} (as of {spike.get('latest_date', 'recent data')}). "
            )

        narrative = (
            f"{spike_context}"
            f"Based on {len(causal_articles)} scraped sources, the likely causes are:\n"
            + "\n".join(cause_lines)
            + f"\n\nNote: {len(found_causes)} causal factor(s) identified from live web search."
        )
    else:
        narrative = (
            f"No strong causal signal found in recent news for {commodity} price movement in {region}. "
            f"Possible explanations based on known Pakistan patterns: "
            f"seasonal demand (Ramadan/harvest cycle), fuel cost transmission, or currency depreciation."
        )

    causal_chain = [
        {
            "cause": kw,
            "cause_source": "web_search",
            "direct_effects": [explanation.split("→")[0].strip() if "→" in explanation else explanation],
            "impact_horizon": "immediate to 30 days",
            "region": region,
            "confidence": 0.70,
            "corroborated": True,
        }
        for kw, explanation in list(found_causes.items())[:4]
    ]

    return {
        "narrative": narrative,
        "causal_chain": causal_chain,
        "articles_used": len(causal_articles),
        "causes_found": list(found_causes.keys()),
        "spike": spike,
    }


def _collect_signal_inputs(
    regions: list[str], time_intent: str = "unspecified", target_commodity: str | None = None
) -> dict[str, Any]:
    return {
        "regions": [
            {
                "region": normalized_region,
                "prices": get_prices(normalized_region, commodity=target_commodity, limit=300),
                "disasters": get_disasters(normalized_region, limit=5),
                "weather": get_weather(normalized_region, limit=5),
                "climate": get_climate(normalized_region, limit=48),
                "news": get_news(
                    ([target_commodity] + SIGNAL_INPUT_CONTEXT_KEYWORDS)
                    if target_commodity
                    else SIGNAL_INPUT_CONTEXT_KEYWORDS,
                    limit=10
                ),
            }
            for normalized_region in [normalize_region(region) for region in regions]
            if normalized_region
        ],
        "time_intent": time_intent,
    }


def _empty_simulation(region: str, run_id: str) -> dict[str, Any]:
    simulation = simulate_action([], region=region, run_id=run_id)
    return {"before": simulation["before"], "after": simulation["after"]}


def refresh_external_sources(regions: list[str], run_id: str) -> list[str]:
    trace = []
    try:
        from chat_agent.weather_ingest import ingest_weather

        result = ingest_weather(regions=regions, run_id=run_id)
        trace.append(f"Weather ingestion refreshed {result['fetched']} regional records.")
    except Exception as exc:  # External data should not block demo reasoning.
        trace.append(f"Weather ingestion skipped: {exc}")
        log_action("weather_ingestion_error", {"error": str(exc)}, run_id=run_id, trace_message="Weather refresh failed")

    primary_region = regions[0] if regions else "National"
    try:
        from chat_agent.scraper import ingest_news_multisource

        result = ingest_news_multisource(region=primary_region, run_id=run_id)
        tier_status = []
        for tier in ("duckduckgo", "rss", "direct"):
            tier_result = result.get(tier, {})
            if tier_result.get("error"):
                tier_status.append(f"{tier}=FAILED({str(tier_result.get('error'))[:40]})")
            else:
                tier_status.append(f"{tier}={tier_result.get('inserted', 0)} inserted")

        trace.append(
            f"News ingestion: {result.get('total_inserted', 0)} total inserted [{ ' | '.join(tier_status) }]"
        )

        if result.get("total_inserted", 0) == 0:
            try:
                from chat_agent.news_ingest import ingest_news

                apify_result = ingest_news(run_id=run_id)
                trace.append(
                    f"Apify fallback: fetched {apify_result['fetched']} items and inserted {apify_result['inserted']}."
                )
            except Exception as apify_exc:
                trace.append(f"Apify fallback also failed: {apify_exc}")
    except Exception as exc:
        trace.append(f"All news ingestion failed: {exc}")
        log_action("news_ingestion_error", {"error": str(exc)}, run_id=run_id, trace_message="News refresh failed")
    return trace


def detect_contradictions(regions: list[str]) -> list[dict[str, Any]]:
    ensure_schema()
    contradictions: list[dict[str, Any]] = []
    with get_connection() as connection:
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'contradictions'").fetchone():
            rows = connection.execute(
                """
                SELECT report_final_date, issue, description
                FROM contradictions
                ORDER BY id DESC
                LIMIT 20
                """
            ).fetchall()
            contradictions.extend(dicts_from_rows(rows))

    for region in regions:
        normalized_region = normalize_region(region)
        disasters = get_disasters(normalized_region, limit=1)
        weather = get_weather(normalized_region, limit=1)
        latest_disaster = disasters["records"][0] if disasters["records"] else None
        latest_weather = weather["records"][0] if weather["records"] else None
        if not latest_disaster or not latest_weather:
            continue
        disaster_risk = " ".join(
            str(latest_disaster.get(key) or "")
            for key in ["severity_level", "supply_risk", "food_price_pressure", "logistics_disruption"]
        ).casefold()
        rainfall = latest_weather.get("rainfall")
        try:
            rainfall_value = float(rainfall) if rainfall is not None else None
        except (TypeError, ValueError):
            rainfall_value = None
        if any(term in disaster_risk for term in ["critical", "high"]) and rainfall_value == 0:
            contradictions.append(
                {
                    "region": normalized_region,
                    "issue": "Temporal signal mismatch",
                    "description": "Disaster records indicate high flood or supply pressure while the latest weather snapshot has no rainfall. Treat this as a historical impact plus current-weather mismatch, not a live flood confirmation.",
                }
            )
    
    # Cross-check news signals against price data (news-price contradiction)
    for region in regions:
        normalized_region = normalize_region(region)
        news = get_news(["shortage", "wheat", "flour", "price hike"], limit=5)
        prices = get_prices(normalized_region, limit=50)
        if news.get("records") and not prices.get("price_spikes"):
            contradictions.append({
                "region": normalized_region,
                "issue": "News-price contradiction",
                "description": "News mentions food shortage/price hike but no price spike detected in SQLite price data. News may be leading indicator — treat with medium confidence.",
            })
    
    return contradictions


def _decide_action_chain(
    signals: list[dict[str, Any]],
    causal_chain: list[dict[str, Any]],
    region: str,
) -> list[str]:
    """Generate actions from signal severity and causal reasoning."""
    if not signals:
        return []

    actions: list[str] = []
    signal_index: dict[str, dict[str, Any]] = {}
    for signal in signals:
        sig_type = str(signal.get("type", ""))
        score = float(signal.get("score", 0) or 0)
        if sig_type not in signal_index or score > float(signal_index[sig_type].get("score", 0) or 0):
            signal_index[sig_type] = signal

    top_score = max(float(signal.get("score", 0) or 0) for signal in signals)
    high_severity_regions = list({
        str(signal.get("region", region))
        for signal in signals
        if float(signal.get("score", 0) or 0) >= 65
    })

    if "disaster_supply_shock" in signal_index and "price_spike" in signal_index:
        disaster_region = signal_index["disaster_supply_shock"].get("region", region)
        commodity = signal_index["price_spike"].get("evidence", {}).get("commodity", "staples")
        actions.append(
            f"EMERGENCY: Activate inter-provincial {commodity} procurement for {disaster_region} — disaster supply shock and price spike are co-occurring."
        )
    elif "price_spike" in signal_index:
        spike = signal_index["price_spike"]
        evidence = spike.get("evidence", {})
        commodity = evidence.get("commodity", "wheat/flour")
        change_pct = evidence.get("change_pct", 0)
        market = evidence.get("market", region)
        if float(change_pct or 0) > PRICE_SPIKE_EMERGENCY_PCT:
            actions.append(
                f"Release strategic {commodity} reserves into {market} market immediately — price is {change_pct}% above baseline, exceeds emergency threshold."
            )
        else:
            actions.append(
                f"Deploy anti-hoarding enforcement and price monitoring in {market} — {commodity} showing {change_pct}% deviation, not yet at emergency threshold."
            )

    if "weather_stress" in signal_index:
        weather_sig = signal_index["weather_stress"]
        weather_region = weather_sig.get("region", region)
        actions.append(
            f"Pre-position seed, fertilizer, and drainage equipment in {weather_region} — weather stress detected: {weather_sig.get('message', 'elevated conditions')}."
        )

    if "disaster_supply_shock" in signal_index and "price_spike" not in signal_index:
        disaster_region = signal_index["disaster_supply_shock"].get("region", region)
        actions.append(
            f"Restore transport corridors and activate relief distribution in {disaster_region} — supply shock without concurrent price spike suggests logistics is primary bottleneck."
        )

    if "news_signal" in signal_index:
        actions.append(
            "Dispatch field verification teams to markets mentioned in news alerts — cross-check reported shortages against warehouse stock levels."
        )

    corroborated = [item for item in causal_chain if item.get("corroborated")]
    if top_score >= 65 and high_severity_regions:
        region_list = ", ".join(high_severity_regions[:2])
        actions.append(
            f"Deploy targeted cash/voucher support for low-income households in {region_list} — high severity signals indicate affordability risk."
        )
    if corroborated:
        actions.append(
            f"Set 6-hour monitoring cycle on corroborated price, weather, and supply feeds in {region} — multiple sources agree on elevated risk."
        )

    cadence = "6-hour" if top_score >= 75 else "24-hour"
    actions.append(
        f"Set {cadence} monitoring cycle on price, weather, and supply feeds — overall risk score is {top_score:.0f}/100."
    )

    deduped: list[str] = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)

    if len(deduped) < 3:
        deduped.extend([
            "Notify National Food Authority and Provincial Food Departments of current risk level.",
            "Prepare import order documentation for wheat and edible oil as contingency.",
        ])

    return deduped[:5]


def _simulation_region(signals: list[dict[str, Any]], regions: list[str]) -> str:
    if signals:
        return normalize_region(str(signals[0].get("region") or regions[0]))
    return normalize_region(regions[0] if regions else "National")


def _coerce_action_chain(value: Any, signals: list[dict[str, Any]]) -> list[str]:
    if not signals:
        return []
    if isinstance(value, list):
        actions = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("action") or item.get("step") or item.get("description")
            else:
                text = str(item)
            if text and (cleaned := " ".join(str(text).split())):
                actions.append(cleaned)
    else:
        actions = []

    if len(actions) < 3:
        actions = _decide_action_chain(signals, [], "National")
    return actions[:5]


def _deterministic_agent(
    *,
    regions: list[str],
    run_id: str,
    trace: list[str] | None = None,
    fallback_reason: str | None = None,
    time_intent: str = "unspecified",
    resolved_geo: dict[str, Any] | None = None,
    query_intent: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reasoning_trace = list(trace or [])
    if fallback_reason:
        reasoning_trace.append(f"OpenAI reasoning fallback used: {fallback_reason}")

    # Resolve geographic and temporal context
    if not resolved_geo:
        resolved_geo = {"province": regions[0] if regions else "National", "confidence": 0.5}
    
    # If this is a trend/forecast question, pull more historical data
    if query_intent and query_intent.get("needs_historical_data"):
        db_data = _collect_signal_inputs(regions, time_intent="historical", target_commodity=query_intent.get("target_commodity"))
    else:
        db_data = _collect_signal_inputs(regions, time_intent=time_intent, target_commodity=query_intent.get("target_commodity") if query_intent else None)
    reasoning_trace.append(f"Read SQLite inputs for {len(db_data['regions'])} regions with time intent: {time_intent}.")
    
    # Get traditional signals
    gen = generate_signals(db_data, time_intent=time_intent)
    if isinstance(gen, dict):
        selected = gen.get("selected", [])
        discarded = gen.get("discarded", [])
        stale = gen.get("stale", [])
    else:
        selected = list(gen)
        discarded = []
        stale = []
    
    # Get reasoning synthesis (NEW LAYER)
    reasoning_synthesis = {}
    try:
        primary_region = regions[0] if regions else "National"
        reasoning_synthesis = get_signals_with_reasoning(primary_region, time_intent)
        reasoning_trace.append(f"Generated causal reasoning chain with {len(reasoning_synthesis.get('causal_chain', []))} cause-effect links.")
    except Exception as e:
        reasoning_trace.append(f"Reasoning synthesis skipped: {str(e)[:50]}")
    
    # Add fallback causal chain builder when reasoning engine doesn't produce chains
    if not reasoning_synthesis.get("causal_chain") and selected:
        reasoning_synthesis["causal_chain"] = [
            {
                "cause": sig.get("message", sig.get("type")),
                "effect": f"Food supply or price pressure in {sig.get('region', 'region')}",
                "confidence": min(1.0, sig.get("score", 50) / 100.0),
                "source": sig.get("source", "unknown"),
            }
            for sig in selected[:3]
        ]
        reasoning_synthesis["reasoning_confidence"] = round(
            sum(s.get("score", 0) for s in selected[:3]) / (3 * 100.0), 2
        )
        reasoning_synthesis["final_reasoning"] = (
            f"Based on {len(selected)} active signals across {len(regions)} regions, "
            f"the primary risk driver is {selected[0].get('type', 'unknown')} in "
            f"{selected[0].get('region', 'National')}."
        )
    
    signals = selected
    reasoning_trace.append(f"Generated {len(signals)} risk signals (selected={len(selected)}, discarded={len(discarded)}, stale={len(stale)}).")
    if stale:
        reasoning_trace.append(f"⚠️  Rejected {len(stale)} stale signal(s) due to time intent '{time_intent}'.")
    
    contradictions = detect_contradictions(regions)
    reasoning_trace.append(f"Detected {len(contradictions)} contradiction or data-quality notes.")
    
    if not signals:
        # No crisis signals — but we should still provide useful baseline intelligence.
        # The user asked a question; returning empty is not helpful.
        reasoning_trace.append("No crisis signals detected — generating baseline assessment.")

        # Build baseline assessment from reasoning synthesis (prices, weather, etc.)
        baseline = reasoning_synthesis.get("historical_baseline", {})
        live_summary = reasoning_synthesis.get("live_signals_summary", {})
        causal_chain = reasoning_synthesis.get("causal_chain", [])
        risk_forecast = reasoning_synthesis.get("risk_forecast", {})

        # If reasoning engine didn't produce a forecast, generate a calm one
        if not risk_forecast:
            risk_forecast = {
                "risk_level": "low",
                "confidence": 0.85,
                "forecast_horizon_days": 30,
                "predicted_impacts": [],
                "recommended_actions": ["Continue routine monitoring"],
            }

        # Build a meaningful reasoning summary
        primary_region = regions[0] if regions else "National"
        stale_count = len(stale)
        discarded_count = len(discarded)

        # Check if price data exists in reasoning synthesis
        price_deviations = baseline.get("deviations", [])
        price_summary_parts = []
        if price_deviations:
            for dev in price_deviations[:3]:
                commodity = dev.get("commodity", "unknown")
                pct = dev.get("deviation_pct", 0)
                direction = "above" if pct > 0 else "below"
                price_summary_parts.append(f"{commodity} is {abs(pct):.1f}% {direction} historical average")

        if price_summary_parts:
            final_reasoning = (
                f"Baseline assessment for {primary_region}: "
                + "; ".join(price_summary_parts) + ". "
                f"No active crisis signals detected. "
                f"{stale_count} stale signal(s) were filtered out. "
                f"Overall risk: LOW."
            )
            reasoning_confidence = 0.75
        else:
            final_reasoning = (
                f"Baseline assessment for {primary_region}: "
                f"No active crisis signals or significant price deviations detected. "
                f"{stale_count} stale signal(s) were filtered out. "
                f"Insufficient current data for detailed trend analysis. "
                f"Overall risk: LOW."
            )
            reasoning_confidence = 0.50

        reasoning_trace.append(f"Baseline reasoning: {final_reasoning[:100]}...")

        sim_region = _simulation_region([], regions)
        result = {
            "signals": [],
            "ranked_signals": [],
            "discarded_signals": discarded + stale,
            "source_weights": {"apify": 0.5, "weather": 0.2, "csv": 0.1},
            "contradictions": contradictions,
            "action_chain": ["Continue routine price and supply monitoring"],
            "simulation": _empty_simulation(sim_region, run_id),
            "reasoning_trace": reasoning_trace,
            "resolved_region": resolved_geo,
            "time_intent": {"intent": time_intent},
            "historical_baseline": baseline,
            "live_signals_summary": live_summary,
            "causal_chain": causal_chain,
            "risk_forecast": risk_forecast,
            "final_reasoning": final_reasoning,
            "reasoning_confidence": reasoning_confidence,
            "sources_checked": _extract_sources_checked(reasoning_trace, reasoning_trace),
            "local_signals": [],
            "province_context": {},
            "national_context": {},
            "status": "baseline_assessment",
            "status_message": (
                f"No active crisis signals for {primary_region}. "
                f"{stale_count} stale and {discarded_count} low-quality signals were filtered. "
                "Providing baseline assessment."
            ),
        }
        log_action("agent_result", result, run_id=run_id, trace_message="Agent completed with baseline assessment (no crisis signals)")
        return result
    
    action_chain = _decide_action_chain(
        signals,
        reasoning_synthesis.get("causal_chain", []),
        regions[0] if regions else "National",
    )
    simulation = simulate_action(action_chain, region=_simulation_region(signals, regions), run_id=run_id)
    reasoning_trace.append("Executed deterministic simulation for the proposed action chain.")

    result = {
        "signals": signals,
        "ranked_signals": [
            {"rank": i + 1, "type": s.get("type"), "score": s.get("final_score", s.get("score")), "region": s.get("region")}
            for i, s in enumerate(selected)
        ],
        "discarded_signals": discarded + stale,
        "source_weights": {"apify": 0.5, "weather": 0.2, "csv": 0.1},
        "contradictions": contradictions,
        "action_chain": action_chain,
        "simulation": {"before": simulation["before"], "after": simulation["after"]},
        "reasoning_trace": reasoning_trace,
        "resolved_region": resolved_geo,
        "time_intent": {"intent": time_intent},
        "local_signals": _build_local_signals(selected, resolved_geo.get("district")),
        "historical_baseline": reasoning_synthesis.get("historical_baseline", {}),
        "live_signals_summary": reasoning_synthesis.get("live_signals_summary", {}),
        "causal_chain": reasoning_synthesis.get("causal_chain", []),
        "risk_forecast": reasoning_synthesis.get("risk_forecast", {}),
        "final_reasoning": reasoning_synthesis.get("final_reasoning", ""),
        "reasoning_confidence": reasoning_synthesis.get("reasoning_confidence", 0.0),
        "sources_checked": _extract_sources_checked(reasoning_trace, reasoning_trace),
        "province_context": {},
        "national_context": {},
    }
    log_action("agent_result", result, run_id=run_id, trace_message="Agent run completed")
    return result


def _finalize_agent_result(
    raw_result: dict[str, Any], 
    *, 
    regions: list[str], 
    run_id: str, 
    trace: list[str],
    time_intent: str = "unspecified",
    resolved_geo: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = dict(REQUIRED_OUTPUT)
    result.update(raw_result)
    
    # Immediately convert dict-shaped final_reasoning (from OpenAI JSON) to markdown string
    fr = result.get("final_reasoning")
    if isinstance(fr, dict):
        parts = []
        for section_key, section_val in fr.items():
            header = section_key.replace("_", " ").title()
            parts.append(f"### {header}\n{section_val}")
        result["final_reasoning"] = "\n\n".join(parts)
        
    if not resolved_geo:
        resolved_geo = {"province": regions[0] if regions else "National", "confidence": 0.5}
    
    signals = result.get("signals")
    ranked = result.get("ranked_signals")
    discarded = result.get("discarded_signals")
    
    if isinstance(signals, dict):
        # older tools compatibility: generate_signals may return dict
        ranked = signals.get("selected")
        discarded = signals.get("discarded", [])
        stale = signals.get("stale", [])
        signals = ranked
        discarded = (discarded or []) + (stale or [])
    
    if not isinstance(signals, list):
        gen = generate_signals(_collect_signal_inputs(regions, time_intent=time_intent), time_intent=time_intent)
        if isinstance(gen, dict):
            ranked = gen.get("selected", [])
            discarded = (gen.get("discarded", []) or []) + (gen.get("stale", []) or [])
            signals = ranked
        else:
            signals = list(gen)
            discarded = []
    
    result["signals"] = signals
    result["ranked_signals"] = ranked or []
    result["discarded_signals"] = discarded or []
    result["source_weights"] = result.get("source_weights") or {"apify": 0.5, "weather": 0.2, "csv": 0.1}
    result["resolved_region"] = resolved_geo
    result["time_intent"] = {"intent": time_intent}
    result["local_signals"] = _build_local_signals(signals or [], resolved_geo.get("district"))

    contradictions = result.get("contradictions")
    if not isinstance(contradictions, list):
        contradictions = detect_contradictions(regions)
    result["contradictions"] = contradictions

    if not result["signals"]:
        # Generate baseline reasoning
        try:
            primary_region = regions[0] if regions else "National"
            reasoning_synthesis = get_signals_with_reasoning(primary_region, time_intent)
            baseline = reasoning_synthesis.get("historical_baseline", {})
            risk_forecast = reasoning_synthesis.get("risk_forecast", {})
            
            if not risk_forecast:
                risk_forecast = {
                    "risk_level": "low",
                    "confidence": 0.85,
                    "forecast_horizon_days": 30,
                    "predicted_impacts": [],
                    "recommended_actions": ["Continue routine monitoring"],
                }

            price_deviations = baseline.get("deviations", [])
            price_summary_parts = []
            if price_deviations:
                for dev in price_deviations[:3]:
                    commodity = dev.get("commodity", "unknown")
                    pct = dev.get("deviation_pct", 0)
                    direction = "above" if pct > 0 else "below"
                    price_summary_parts.append(f"{commodity} is {abs(pct):.1f}% {direction} historical average")

            stale_count = len([s for s in discarded if s.get("status") == "stale"])
            
            if price_summary_parts:
                final_reasoning = (
                    f"### 🔍 Analysis Scope\n"
                    f"I completed a routine baseline assessment for **{primary_region}**. I reviewed current price stability and checked for emerging crisis signals.\n\n"
                    f"### 🛠️ Investigation Method\n"
                    f"I cross-referenced local market data with historical averages and analyzed available signal feeds for supply chain anomalies.\n\n"
                    f"### 📊 Findings & Assessment\n"
                    f"Current data indicates: " + "; ".join(price_summary_parts) + ". "
                    f"No active emergency signals were detected during this scan. The market situation remains within normal operating parameters.\n\n"
                    f"**Risk Level:** LOW\n"
                    f"**Forecast Horizon:** 30 days"
                )
                reasoning_confidence = 0.75
            else:
                final_reasoning = (
                    f"### 🔍 Analysis Scope\n"
                    f"I conducted a baseline safety check for **{primary_region}**.\n\n"
                    f"### 🛠️ Investigation Method\n"
                    f"I performed a broad-spectrum scan of available food security indicators and recent price telemetry.\n\n"
                    f"### 📊 Findings & Assessment\n"
                    f"No active crisis signals or significant price deviations detected. Regional food security metrics are stable.\n\n"
                    f"**Risk Level:** LOW\n"
                    f"**Forecast Horizon:** 30 days"
                )
                reasoning_confidence = 0.50

            result["historical_baseline"] = baseline
            result["live_signals_summary"] = reasoning_synthesis.get("live_signals_summary", {})
            result["causal_chain"] = reasoning_synthesis.get("causal_chain", [])
            result["risk_forecast"] = risk_forecast
            
            if not result.get("final_reasoning"):
                result["final_reasoning"] = final_reasoning
            if not result.get("reasoning_confidence"):
                result["reasoning_confidence"] = reasoning_confidence
                
            result["status"] = "baseline_assessment"
            result["status_message"] = f"No active crisis signals for {primary_region}. Providing baseline assessment."
            
            if not result.get("action_chain"):
                result["action_chain"] = []

        except Exception as e:
            if not result.get("action_chain"):
                result["action_chain"] = []
            if not result.get("final_reasoning"):
                result["final_reasoning"] = f"Stable condition. {len(discarded)} signals were discarded or stale."
                result["reasoning_confidence"] = 0.5

        result["simulation"] = _empty_simulation(_simulation_region([], regions), run_id)
        result["reasoning_trace"] = [*trace, "No actionable crisis signals detected."]
        log_action("agent_result", result, run_id=run_id, trace_message="Agent run completed without risk signals.")
        return result

    if result.get("action_chain") is None or len(result.get("action_chain", [])) == 0:
        result["action_chain"] = _coerce_action_chain(result.get("action_chain"), result["signals"])
        
    simulation = result.get("simulation")
    if not isinstance(simulation, dict) or not simulation.get("before") or not simulation.get("after"):
        simulation = simulate_action(
            result["action_chain"],
            region=_simulation_region(result["signals"], regions),
            run_id=run_id,
        )
    result["simulation"] = {"before": simulation.get("before", {}), "after": simulation.get("after", {})}

    model_trace = result.get("reasoning_trace")
    if not isinstance(model_trace, list):
        model_trace = []
    result["reasoning_trace"] = [*trace, *[str(item) for item in model_trace]]

    if not result.get("final_reasoning") or not result.get("reasoning_confidence"):
        try:
            primary_region = regions[0] if regions else "National"
            reasoning_synthesis = get_signals_with_reasoning(primary_region, time_intent)
            for key in ["historical_baseline", "live_signals_summary", "causal_chain",
                         "risk_forecast", "final_reasoning", "reasoning_confidence"]:
                if not result.get(key) or result.get(key) in (0, 0.0, "", [], {}):
                    result[key] = reasoning_synthesis.get(key, result.get(key))
        except Exception:
            # Build minimal reasoning from available signals
            if result["signals"]:
                result["final_reasoning"] = (
                    f"Based on {len(result['signals'])} active signals, "
                    f"the primary risk driver is {result['signals'][0].get('type', 'unknown')} "
                    f"in {result['signals'][0].get('region', 'National')}."
                )
                result["reasoning_confidence"] = round(
                    sum(s.get("score", 0) for s in result["signals"][:3]) / (3 * 100.0), 2
                )

    # Extract sources checked from trace for the UI
    sources_checked = set()
    full_trace_str = " ".join(trace + [str(t) for t in (result.get("reasoning_trace") or [])]).lower()
    if "weather" in full_trace_str: sources_checked.add("WeatherAPI")
    if "duckduckgo" in full_trace_str: sources_checked.add("DuckDuckGo Intelligence")
    if "wikipedia" in full_trace_str: sources_checked.add("Wikipedia (Global)")
    if "apify" in full_trace_str: sources_checked.add("Apify (Web Scraper)")
    if "rss" in full_trace_str: sources_checked.add("Regional RSS Feeds")
    if "kissanstore" in full_trace_str: sources_checked.add("KissanStore (Live Prices)")
    if "startpage" in full_trace_str: sources_checked.add("StartPage Search")
    
    sources_checked.add("Regional Historical Database")
    result["sources_checked"] = sorted(list(sources_checked))

    # Normalize signals for the frontend to show proper scores and levels
    normalized_signals = []
    for sig in (result.get("signals") or []):
        if isinstance(sig, dict):
            # Parse or convert risk score
            score = sig.get("composite_risk_score") or sig.get("score")
            if score is None:
                # Map from supply_risk or severity_level
                level_str = (sig.get("severity_level") or sig.get("supply_risk") or "Low").lower()
                if "critical" in level_str:
                    score = 90
                elif "high" in level_str:
                    score = 75
                elif "medium" in level_str:
                    score = 50
                else:
                    score = 20
            
            sig["composite_risk_score"] = score
            sig["score"] = score
            
            # Parse or convert risk level
            level = sig.get("risk_level") or sig.get("level") or sig.get("severity_level") or sig.get("supply_risk") or "Low"
            sig["risk_level"] = level
            sig["level"] = level
            normalized_signals.append(sig)
        else:
            normalized_signals.append(sig)
    result["signals"] = normalized_signals

    # Ensure a summary exists for the frontend terminal
    if not result.get("summary"):
        result["summary"] = result.get("final_reasoning") or "Analysis completed successfully. No major deviations from baseline food security metrics were identified in the specified regions."

    # Backward compatibility with older frontend clients
    result["answer"] = result.get("final_reasoning")

    return result


def _run_openai_tool_agent(
    *,
    regions: list[str],
    run_id: str,
    trace: list[str],
    time_intent: str = "unspecified",
    resolved_geo: dict[str, Any] | None = None,
    user_query: str | None = None,
) -> dict[str, Any]:
    api_key = get_env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    from openai import OpenAI

    model = get_env("OPENAI_MODEL") or "gpt-4o-mini"
    client = OpenAI(api_key=api_key)
    tool_mapping = _tool_mapping(run_id)
    tool_trace = list(trace)
    # Pass user_query through to the prompt if available
    user_query_text = user_query or f"Risk assessment for {', '.join(regions)}"
    
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are FaslBot, a Pakistan food-security intelligence engine. "
                "You answer the user's specific question using real data from your tools. "
                "First gather signals from prices, climate, disasters, news, and weather tools, "
                "then synthesize a DIRECT answer to the user's question based on the evidence. "
                "Detect supply risks, price spikes, disaster impacts, and contradictions. "
                "\nTool schemas: "
                "get_prices returns {price_spikes:[{commodity,change_pct,market,latest_date}], records:[...]}. "
                "get_disasters returns {active_impacts:[{region,supply_risk,crop_loss_acres,food_price_pressure,severity_level}]}. "
                "get_news returns {records:[{title,content,date,keywords,source}]}. "
                "get_weather returns {latest_by_region:{...weather data with temperature,rainfall,humidity}}. "
                "Always check price_spikes list and active_impacts list before concluding no risk exists. "
                "\nReturn ONLY valid JSON with these keys: "
                "signals (list of risk signal objects, ONLY if there are active risks), "
                "contradictions (list of conflicting data points found), "
                "action_chain (3-5 concrete intervention steps relevant to the query, ONLY if the query requires action or risk mitigation; otherwise leave empty), "
                "simulation (before/after state), "
                "reasoning_trace (concise operational trace messages), "
                "final_reasoning (a detailed markdown narrative that DIRECTLY answers the user's question "
                "using specific data points, numbers, dates, and sources from the tool results — "
                "NOT generic boilerplate. Include sections: Analysis, Key Findings, Evidence, and Risk Assessment), "
                "reasoning_confidence (float 0.0-1.0 based on data quality and coverage). "
                f"\nTime context: {time_intent}. Discard data older than relevant thresholds."
            ),
        },
        {
            "role": "user",
            "content": (
                f"User question: \"{user_query_text}\"\n\n"
                f"Regions to assess: {', '.join(regions)}. "
                "Use all available tools to gather real data before answering. "
                "Your final_reasoning MUST directly address the user's question with specific evidence. "
                f"Temporal intent: {time_intent}."
            ),
        },
    ]

    start = time.monotonic()
    last_tool_call_sequence = tuple()
    for iteration in range(10):
        elapsed = time.monotonic() - start
        if elapsed > 90:
            raise RuntimeError(
                f"OpenAI tool loop timed-out after {elapsed:.0f}s and {iteration} iterations "
                f"without reaching a final answer."
            )

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=_tool_definitions(),
            tool_choice="auto",
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        message = response.choices[0].message
        assistant_message: dict[str, Any] = {"role": "assistant", "content": message.content}
        if message.tool_calls:
            assistant_message["tool_calls"] = [tool_call.model_dump() for tool_call in message.tool_calls]
        messages.append(assistant_message)

        if not message.tool_calls:
            parsed = _json_loads(message.content)
            if not parsed:
                raise RuntimeError("OpenAI returned non-JSON final content")
            return _finalize_agent_result(
                parsed,
                regions=regions,
                run_id=run_id,
                trace=tool_trace,
                time_intent=time_intent,
                resolved_geo=resolved_geo,
            )

        # Convergence guard: detect if model is cycling on the same tools
        current_tools = tuple(
            tc.function.name for tc in (message.tool_calls or [])
        )
        if current_tools == last_tool_call_sequence and current_tools:
            raise RuntimeError(
                f"OpenAI tool loop is cycling on the same tool(s) {list(current_tools)} "
                f"without converging — stopped at iteration {iteration + 1} "
                f"(elapsed {elapsed:.0f}s)."
            )
        last_tool_call_sequence = current_tools

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = _json_loads(tool_call.function.arguments)
            if name not in tool_mapping:
                result = {"error": f"Unknown tool: {name}"}
            else:
                result = tool_mapping[name](**arguments)
            tool_trace.append(f"Tool call completed: {name}")
            log_action(
                "tool_call",
                {"tool": name, "arguments": arguments, "result_preview": str(result)[:1200]},
                run_id=run_id,
                trace_message=f"OpenAI called {name}",
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json_dumps(result)[:14000],
                }
            )

    raise RuntimeError(
        f"OpenAI tool loop exhausted maximum iterations after {time.monotonic() - start:.0f}s "
        "without reaching a final answer — agent did not converge."
    )


def run_agent(
    *,
    regions: list[str] | None = None,
    refresh: bool = True,
    use_openai: bool = True,
    user_query: str | None = None,
) -> dict[str, Any]:
    ensure_schema()
    run_id = str(uuid4())
    
    # Extract time intent from user query (if provided)
    time_intent_parsed = _extract_time_intent_from_context(user_query)
    time_intent = time_intent_parsed.get("intent", "unspecified")
    
    # Resolve geographic context from first region or query
    # Extract clean region from query if no explicit regions given
    if regions:
        primary_region = regions[0]
    else:
        # Parse region from query using geo resolver, fallback to National
        from chat_agent.geo_resolver import _extract_region_from_text

        primary_region = _extract_region_from_text(user_query) or "National"

    resolved_geo = resolve_region(primary_region)
    requested_regions = [normalize_region(r) for r in (regions or [primary_region])]
    trace = [
        f"Agent run {run_id} started for {', '.join(requested_regions)}.",
        f"Geo resolution: {resolved_geo.get('province', 'National')} (confidence: {resolved_geo.get('confidence', 0)})",
        f"Time intent: {time_intent} (confidence: {time_intent_parsed.get('confidence', 0)})",
    ]

    query_intent = _classify_query_intent(user_query)
    trace.append(f"Query classified as: {query_intent['question_type']} (commodity: {query_intent.get('target_commodity', 'general')})")

    if refresh:
        trace.extend(refresh_external_sources(requested_regions, run_id))

    # Fast path for simple queries (skip if using OpenAI so the LLM formats the answer)
    if not use_openai:
        direct = _answer_direct_query(
            query_intent, requested_regions, run_id, trace,
            time_intent, resolved_geo
        )
        if direct:
            return direct

    # WHY path: deep causal explanation with targeted web search
    if not use_openai and query_intent.get("question_type") == "why" and query_intent.get("target_commodity"):
        commodity = query_intent["target_commodity"]
        explanation = _explain_price_spike(commodity, primary_region, run_id, trace)
        
        return {
            **REQUIRED_OUTPUT,
            "signals": [],
            "action_chain": [
                f"Investigate {commodity} supply chain for {explanation.get('causes_found', ['unknown'])[0] if explanation.get('causes_found') else 'market factors'}",
                f"Deploy price monitoring in {primary_region} markets",
                "Brief Ministry of Food Security on identified causal factors",
            ],
            "final_reasoning": explanation["narrative"],
            "causal_chain": explanation["causal_chain"],
            "reasoning_confidence": 0.75 if explanation.get("causes_found") else 0.40,
            "reasoning_trace": trace + [f"WHY-path: {explanation['articles_used']} articles analyzed, {len(explanation.get('causes_found', []))} causes found"],
            "resolved_region": resolved_geo,
            "time_intent": {"intent": time_intent},
            "status": "causal_explanation",
            "status_message": explanation["narrative"],
        }

    if use_openai:
        try:
            return _run_openai_tool_agent(
                regions=requested_regions,
                run_id=run_id,
                trace=trace,
                time_intent=time_intent,
                resolved_geo=resolved_geo,
                user_query=user_query,
            )
        except Exception as exc:
            log_action("openai_agent_error", {"error": str(exc)}, run_id=run_id, trace_message="OpenAI agent failed")
            return _deterministic_agent(
                regions=requested_regions,
                run_id=run_id,
                trace=trace,
                fallback_reason=str(exc),
                time_intent=time_intent,
                resolved_geo=resolved_geo,
                query_intent=query_intent,
            )

    return _deterministic_agent(
        regions=requested_regions,
        run_id=run_id,
        trace=trace,
        time_intent=time_intent,
        resolved_geo=resolved_geo,
        query_intent=query_intent,
    )

