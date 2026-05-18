from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from chat_agent.config import (
    FOOD_SECURITY_KEYWORDS,
    PRICE_SPIKE_EMERGENCY_PCT,
    PRICE_SPIKE_WARNING_PCT,
    SIGNAL_MIN_FINAL_SCORE,
    SIGNAL_MIN_RECENCY,
    SIGNAL_MIN_RELEVANCE,
    WEIGHT_CREDIBILITY,
    WEIGHT_RECENCY,
    WEIGHT_RELEVANCE,
)
from chat_agent.db import (
    DISASTERS_TABLE,
    NEWS_TABLE,
    WEATHER_TABLE,
    dicts_from_rows,
    ensure_schema,
    get_connection,
    log_action,
    normalize_region,
)
from chat_agent.geo_resolver import resolve_region
from chat_agent.temporal_resolver import (
    compute_age_days,
    compute_recency_score_v2,
    filter_signals_by_time,
    parse_time_intent,
)


def _severity_from_score(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 55:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _numeric(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


# Scoring and priority helpers
SOURCE_PRIORITY = {
    "apify": 1,
    "weather": 2,
    "disaster": 3,
    "price_csv": 4,
    "climate_csv": 5,
}


def _compute_recency_score(timestamp_str: str | None) -> float:
    """Return recency score in 0..1 based on ACTUAL publication date.
    If timestamp_str is None or unparseable, returns 0.0 — NOT 1.0.
    This prevents old articles with null dates from scoring as 'fresh'.
    """
    if not timestamp_str:
        return 0.0
    return compute_recency_score_v2(timestamp_str, time_intent="recent")


def _compute_relevance_for_news(record: dict[str, Any]) -> float:
    """Simple heuristic: proportion of allowed keywords present (0..1)."""
    text = " ".join(filter(None, [str(record.get("title") or ""), str(record.get("content") or "")] )).casefold()
    if not text:
        return 0.0
    keywords = FOOD_SECURITY_KEYWORDS
    matches = 0
    for kw in keywords:
        if kw in text:
            matches += 1
    return min(1.0, matches / max(1.0, len(keywords)))


def _compute_relevance_for_signal(signal: dict[str, Any]) -> float:
    # If numeric score exists, normalize to 0..1
    if isinstance(signal.get("score"), (int, float)):
        return max(0.0, min(1.0, float(signal.get("score")) / 100.0))
    # For disaster/weather types without numeric score, use severity mapping
    sev = str(signal.get("severity") or "").casefold()
    if sev == "critical":
        return 1.0
    if sev == "high":
        return 0.8
    if sev == "medium":
        return 0.5
    return 0.2


def _source_credibility_for_signal(source_key: str) -> float:
    key = (source_key or "").casefold()
    if "apify" in key or "news" in key:
        return 1.0
    if "weather" in key:
        return 0.9
    if "disaster" in key or "ndma" in key or "pdma" in key:
        return 0.95
    if "price" in key or "prices" in key or "csv" in key:
        return 0.3
    if "climate" in key:
        return 0.2
    return 0.4


def _final_signal_score(relevance: float, recency: float, credibility: float) -> float:
    return relevance * WEIGHT_RELEVANCE + recency * WEIGHT_RECENCY + credibility * WEIGHT_CREDIBILITY


# ── Signal Quality Gates ──────────────────────────────────────────────────
MIN_RELEVANCE = SIGNAL_MIN_RELEVANCE    # reject signals below this relevance
MIN_RECENCY = SIGNAL_MIN_RECENCY       # reject signals with no parseable date
MIN_CREDIBILITY = 0.20                 # reject signals below this credibility
MIN_FINAL_SCORE = SIGNAL_MIN_FINAL_SCORE  # reject signals below this final score


def rank_and_select_signals(signals: list[dict[str, Any]], top_k_min: int = 3, top_k_max: int = 7) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rank signals by computed final_score and return (ranked, discarded).

    Quality gates applied:
    - Reject relevance < MIN_RELEVANCE (noise)
    - Reject recency = 0 for news signals (no parseable date)
    - Reject final_score < MIN_FINAL_SCORE
    """
    for sig in signals:
        # compute relevance, recency, credibility
        relevance = _compute_relevance_for_signal(sig)

        # ── RECENCY: use ACTUAL article date ONLY, never created_at ──
        # created_at is the scrape time (always today) — using it masks
        # the real article age and inflates recency to 1.0 for old articles.
        ts_val = None
        evidence = sig.get("evidence")
        if isinstance(evidence, dict):
            # Structured evidence (disaster, price) — use date/timestamp only
            ts_val = (
                evidence.get("date")
                or evidence.get("signal_timestamp")
                or evidence.get("timestamp")
            )
        elif isinstance(evidence, list) and evidence:
            # News evidence list — use the best actual article date
            for ev_item in evidence:
                if not isinstance(ev_item, dict):
                    continue
                ev_date = ev_item.get("date")  # actual publish date ONLY
                if ev_date:
                    ts_val = ev_date
                    break
        # Fallback to signal-level date (NOT created_at)
        if not ts_val:
            ts_val = sig.get("date") or sig.get("timestamp")

        recency = _compute_recency_score(ts_val)
        credibility = _source_credibility_for_signal(sig.get("source") or sig.get("type") or "")
        final = _final_signal_score(relevance, recency, credibility)

        # boost Apify/news and weather slightly to ensure override of CSV
        src = str(sig.get("source") or "").casefold()
        if "apify" in src or "duckduckgo" in src or sig.get("type") == "news_signal":
            final = min(1.0, final + 0.08)
        if "weather" in src or sig.get("type") == "weather_stress":
            final = min(1.0, final + 0.05)

        sig["relevance_score"] = round(relevance, 3)
        sig["recency_score"] = round(recency, 3)
        sig["source_credibility"] = round(credibility, 3)
        sig["final_score"] = round(final * 100.0, 2)

    # ── Quality gates: reject noise before ranking ──
    quality_passed = []
    quality_rejected = []
    for sig in signals:
        is_news = sig.get("type") == "news_signal"
        rejected_reason = None

        # Gate 1: Relevance gate (reject low-relevance noise)
        if sig.get("relevance_score", 0) < MIN_RELEVANCE and is_news:
            rejected_reason = f"low_relevance ({sig.get('relevance_score', 0):.2f} < {MIN_RELEVANCE})"

        # Gate 2: Recency gate (reject news with no real date)
        if is_news and sig.get("recency_score", 0) < MIN_RECENCY:
            rejected_reason = f"no_publish_date (recency={sig.get('recency_score', 0):.2f})"

        # Gate 3: Final score gate
        if sig.get("final_score", 0) < MIN_FINAL_SCORE:
            rejected_reason = f"low_final_score ({sig.get('final_score', 0):.1f} < {MIN_FINAL_SCORE})"

        if rejected_reason:
            sig["rejected_reason"] = rejected_reason
            quality_rejected.append(sig)
        else:
            quality_passed.append(sig)

    ranked = sorted(quality_passed, key=lambda s: s.get("final_score", 0), reverse=True)
    k = max(top_k_min, min(top_k_max, len(ranked)))
    selected = ranked[:k]
    discarded = ranked[k:] + quality_rejected
    return selected, discarded


def generate_signals_with_time_context(
    db_data: dict[str, Any], 
    time_intent: str = "unspecified"
) -> dict[str, Any]:
    """
    Generate and filter signals based on time intent.
    Returns {
        "selected": [...],
        "discarded": [...],
        "stale": [...],
        "time_intent": ...,
        "time_validation": {...}
    }
    """
    regions = db_data.get("regions")
    if not isinstance(regions, list):
        return {
            "selected": [],
            "discarded": [],
            "stale": [],
            "time_intent": time_intent,
            "time_validation": {"max_age_days": None},
        }

    signals: list[dict[str, Any]] = []
    for region_data in regions:
        if not isinstance(region_data, dict):
            continue

        normalized_region = normalize_region(region_data.get("region"))
        if not normalized_region:
            continue

        price_data = region_data.get("prices") if isinstance(region_data.get("prices"), dict) else {}
        disaster_data = region_data.get("disasters") if isinstance(region_data.get("disasters"), dict) else {}
        weather_data = region_data.get("weather") if isinstance(region_data.get("weather"), dict) else {}
        news_data = region_data.get("news") if isinstance(region_data.get("news"), dict) else {}

        if price_data.get("price_spikes"):
            top_spike = price_data["price_spikes"][0]
            score = min(100.0, 45.0 + float(top_spike["change_pct"]))
            signals.append(
                {
                    "region": normalized_region,
                    "type": "price_spike",
                    "source": "price_csv",
                    "severity": _severity_from_score(score),
                    "score": round(score, 2),
                    "message": f"{top_spike['commodity']} is {top_spike['change_pct']}% above its recent baseline.",
                    "evidence": top_spike,
                    "timestamp": top_spike.get("latest_date"),
                    "date": top_spike.get("latest_date"),
                    "created_at": top_spike.get("latest_date"),
                }
            )

        for impact in disaster_data.get("active_impacts", [])[:2]:
            if not isinstance(impact, dict):
                continue
            risk_text = " ".join(
                str(impact.get(key) or "")
                for key in ["severity_level", "supply_risk", "food_price_pressure", "logistics_disruption"]
            ).casefold()
            if any(term in risk_text for term in ["critical", "high"]):
                crop_loss = _numeric(impact.get("crop_loss_acres")) or 0.0
                score = min(100.0, 60.0 + min(crop_loss / 100000.0, 25.0))
                signals.append(
                    {
                        "region": normalized_region,
                        "type": "disaster_supply_shock",
                        "source": "disaster",
                        "severity": _severity_from_score(score),
                        "score": round(score, 2),
                        "message": "Disaster reporting indicates elevated supply, logistics, or food-price pressure.",
                        "evidence": impact,
                        "timestamp": impact.get("signal_timestamp"),
                    }
                )

        latest_weather = next(iter(weather_data.get("latest_by_region", {}).values()), None)
        if isinstance(latest_weather, dict):
            temperature = _numeric(latest_weather.get("temperature"))
            rainfall = _numeric(latest_weather.get("rainfall"))
            humidity = _numeric(latest_weather.get("humidity"))
            weather_score = 0.0
            drivers = []
            if temperature is not None and temperature >= 40:
                weather_score += 40
                drivers.append("extreme heat")
            if rainfall is not None and rainfall >= 20:
                weather_score += 35
                drivers.append("heavy rainfall")
            if humidity is not None and humidity >= 85:
                weather_score += 15
                drivers.append("high humidity")
            if weather_score:
                score = 35 + weather_score
                signals.append(
                    {
                        "region": normalized_region,
                        "type": "weather_stress",
                        "source": "weather",
                        "severity": _severity_from_score(score),
                        "score": round(min(score, 100), 2),
                        "message": f"Current weather flags {', '.join(drivers)}.",
                        "evidence": latest_weather,
                        "timestamp": latest_weather.get("timestamp"),
                    }
                )

        if news_data.get("records"):
            # Compute dynamic news signal score based on content quality
            news_records = news_data["records"][:5]

            # ── On-the-fly date re-extraction for old DB records ──
            # Old records may have date=null. Try to extract the real
            # publish date from content/title text before scoring.
            try:
                from chat_agent.news_ingest import _extract_date_from_text
            except ImportError:
                _extract_date_from_text = None
            for rec in news_records:
                if not rec.get("date") and _extract_date_from_text:
                    extracted = _extract_date_from_text(
                        str(rec.get("content", "")) + " " + str(rec.get("title", ""))
                    )
                    if extracted:
                        rec["date"] = extracted

            # Score based on: keyword density, number of sources, recency
            total_relevance = 0.0
            source_set = set()
            best_recency = 0.0
            for rec in news_records:
                total_relevance += _compute_relevance_for_news(rec)
                source_set.add(rec.get("source", ""))
                # Use ACTUAL article date ONLY — never created_at
                rec_date = rec.get("date")
                rec_recency = _compute_recency_score(rec_date)
                best_recency = max(best_recency, rec_recency)
            avg_relevance = total_relevance / max(1, len(news_records))
            source_diversity = min(1.0, len(source_set) / 3.0)

            # Penalize heavily if no real dates found
            date_quality = 1.0 if best_recency > 0 else 0.2
            news_score = min(85, max(15, round(
                avg_relevance * 30 + best_recency * 30 + source_diversity * 10 + date_quality * 15 + 15
            )))
            news_severity = _severity_from_score(news_score)

            # Determine actual source from evidence records
            actual_sources = list(source_set - {""})
            ingestion_source = "news_scraper"
            if actual_sources:
                ingestion_source = actual_sources[0] if len(actual_sources) == 1 else "multi_source"

            # Use the best actual article date for the signal timestamp
            best_article_date = None
            for rec in news_records:
                if rec.get("date"):
                    best_article_date = rec["date"]
                    break

            signals.append(
                {
                    "region": normalized_region,
                    "type": "news_signal",
                    "source": ingestion_source,
                    "severity": news_severity,
                    "score": news_score,
                    "message": f"Found {len(news_records)} news articles with food-security keywords (relevance: {avg_relevance:.2f}, sources: {len(source_set)}, date_quality: {date_quality:.0%}).",
                    "evidence": news_records[:3],
                    "timestamp": best_article_date,  # ONLY real article date
                    "date": best_article_date,         # ONLY real article date
                    "created_at": news_records[0].get("created_at"),
                }
            )

        # Add climate anomaly signal from CSV data if available
        climate_data = region_data.get("climate") if isinstance(region_data.get("climate"), dict) else {}
        climate_records = climate_data.get("records", [])
        if climate_records:
            temps = [r.get("temperature") for r in climate_records if r.get("temperature") is not None]
            if temps:
                from statistics import mean as _mean

                avg_temp = _mean(temps)
                if avg_temp > CLIMATE_TEMP_ANOMALY_THRESHOLD:  # above Pakistan seasonal norm
                    signals.append(
                        {
                            "region": normalized_region,
                            "type": "climate_anomaly",
                            "source": "climate_csv",
                            "severity": "medium" if avg_temp < 32 else "high",
                            "score": min(100.0, 35.0 + (avg_temp - CLIMATE_TEMP_ANOMALY_THRESHOLD) * 3),
                            "message": f"Historical climate avg {avg_temp:.1f}°C indicates elevated temperature stress.",
                            "evidence": {"avg_temp": avg_temp, "records_used": len(temps)},
                            "timestamp": climate_records[0].get("created_at"),
                            "created_at": climate_records[0].get("created_at"),
                        }
                    )

    # Filter by time intent first: separate stale from valid
    valid, stale = filter_signals_by_time(signals, time_intent)
    
    # Rank valid signals
    selected, discarded = rank_and_select_signals(valid, top_k_min=3, top_k_max=7)
    
    for s in selected:
        s.setdefault("status", "selected")
    for s in discarded:
        s.setdefault("status", "discarded")
    for s in stale:
        s.setdefault("status", "stale")

    return {
        "selected": selected,
        "discarded": discarded,
        "stale": stale,
        "time_intent": time_intent,
        "time_validation": {
            "max_age_days": 7 if time_intent == "real_time" else 30 if time_intent == "recent" else 365 * 2,
            "intent_confidence": 0.5,  # Will be updated by agent
        },
    }


def get_prices(region: str = "National", commodity: str | None = None, limit: int = 120) -> dict[str, Any]:
    ensure_schema()
    normalized_region = normalize_region(region)
    bounded_limit = max(10, min(int(limit), 1000))
    params: list[Any] = []
    clauses = ["price IS NOT NULL"]
    if normalized_region != "National":
        clauses.append("admname_normalized = ?")
        params.append(normalized_region)
    if commodity:
        clauses.append("cmname LIKE ?")
        params.append(f"%{commodity}%")

    where_sql = " AND ".join(clauses)
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT date, cmname, price, currency, admname, admname_normalized, mktname, category
            FROM prices
            WHERE {where_sql}
            ORDER BY date DESC
            LIMIT ?
            """,
            (*params, bounded_limit),
        ).fetchall()

    records = dicts_from_rows(rows)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("cmname"))].append(record)

    price_spikes = []
    for cmname, commodity_rows in grouped.items():
        ordered = sorted(commodity_rows, key=lambda item: str(item.get("date") or ""), reverse=True)
        latest_price = _numeric(ordered[0].get("price")) if ordered else None
        previous_prices = [
            value
            for item in ordered[1:7]
            if (value := _numeric(item.get("price"))) is not None
        ]
        if latest_price is None or not previous_prices:
            continue
        baseline = mean(previous_prices)
        if baseline <= 0:
            continue
        change_pct = ((latest_price - baseline) / baseline) * 100
        if change_pct >= PRICE_SPIKE_WARNING_PCT:
            price_spikes.append(
                {
                    "commodity": cmname,
                    "latest_price": round(latest_price, 2),
                    "baseline_price": round(baseline, 2),
                    "change_pct": round(change_pct, 2),
                    "latest_date": ordered[0].get("date"),
                    "market": ordered[0].get("mktname"),
                    "currency": ordered[0].get("currency"),
                }
            )

    kissan_wheat_prices = []
    if commodity is None or "wheat" in commodity.lower():
        try:
            from chat_agent.scraper import scrape_kissan_wheat_prices
            kissan_wheat_prices = scrape_kissan_wheat_prices()
        except Exception:
            pass

    return {
        "region": normalized_region,
        "commodity": commodity,
        "records": records,
        "price_spikes": sorted(price_spikes, key=lambda item: item["change_pct"], reverse=True)[:10],
        "live_wheat_rates": kissan_wheat_prices,
    }


def get_disasters(region: str = "National", limit: int = 20) -> dict[str, Any]:
    ensure_schema()
    normalized_region = normalize_region(region)
    bounded_limit = max(1, min(int(limit), 100))
    params: list[Any] = []
    where_sql = "1 = 1"
    if normalized_region != "National":
        where_sql = "region_normalized = ?"
        params.append(normalized_region)

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT *
            FROM {DISASTERS_TABLE}
            WHERE {where_sql}
            ORDER BY signal_timestamp DESC, id DESC
            LIMIT ?
            """,
            (*params, bounded_limit),
        ).fetchall()
    records = dicts_from_rows(rows)
    active_impacts = [
        {
            "region": item.get("region_normalized") or item.get("region"),
            "severity_level": item.get("severity_level"),
            "supply_risk": item.get("supply_risk"),
            "food_price_pressure": item.get("food_price_pressure"),
            "logistics_disruption": item.get("logistics_disruption"),
            "crop_loss_acres": item.get("crop_loss_acres"),
            "high_impact_commodities": item.get("high_impact_commodities"),
            "signal_timestamp": item.get("signal_timestamp"),
        }
        for item in records
    ]
    return {"region": normalized_region, "records": records, "active_impacts": active_impacts}


def get_climate(region: str = "National", limit: int = 48) -> dict[str, Any]:
    ensure_schema()
    bounded_limit = max(12, min(int(limit), 240))
    # Note: Historical climate table does not currently support regional breakdown in this schema.
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT metric, year, month, observed_at, value
            FROM climate
            ORDER BY observed_at DESC
            LIMIT ?
            """,
            (bounded_limit,),
        ).fetchall()
    records = dicts_from_rows(rows)

    by_metric: dict[str, list[float]] = defaultdict(list)
    for item in records:
        value = _numeric(item.get("value"))
        if value is not None:
            by_metric[str(item.get("metric"))].append(value)

    summary = {
        metric: {
            "latest_value": values[0] if values else None,
            "recent_average": round(mean(values[:12]), 2) if values else None,
            "sample_count": len(values),
        }
        for metric, values in by_metric.items()
    }
    return {
        "region": normalize_region(region),
        "records": records,
        "summary": summary,
        "region_filter_applied": False,   # climate CSV is national; region accepted but not applied in query
    }


def get_news(keywords: str | list[str] | None = None, limit: int = 20) -> dict[str, Any]:
    ensure_schema()
    bounded_limit = max(1, min(int(limit), 100))
    if keywords is None:
        terms: list[str] = []
    elif isinstance(keywords, str):
        terms = [term.strip() for term in keywords.split(",") if term.strip()]
    else:
        terms = [str(term).strip() for term in keywords if str(term).strip()]

    params: list[Any] = []
    where_sql = "1 = 1"
    if terms:
        clauses = []
        for term in terms:
            clauses.append("(title LIKE ? OR content LIKE ? OR keywords LIKE ?)")
            like_term = f"%{term}%"
            params.extend([like_term, like_term, like_term])
        where_sql = " OR ".join(clauses)

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT title, content, date, source, url, keywords, created_at
            FROM {NEWS_TABLE}
            WHERE {where_sql}
            ORDER BY COALESCE(date, created_at) DESC, id DESC
            LIMIT ?
            """,
            (*params, bounded_limit),
        ).fetchall()
    return {"keywords": terms, "records": dicts_from_rows(rows)}


def get_weather(region: str = "National", limit: int = 20) -> dict[str, Any]:
    ensure_schema()
    normalized_region = normalize_region(region)
    bounded_limit = max(1, min(int(limit), 100))
    params: list[Any] = []
    where_sql = "1 = 1"
    if normalized_region != "National":
        where_sql = "region_normalized = ?"
        params.append(normalized_region)

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT region, region_normalized, temperature, rainfall, humidity, timestamp, source
            FROM {WEATHER_TABLE}
            WHERE {where_sql}
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
            """,
            (*params, bounded_limit),
        ).fetchall()
    records = dicts_from_rows(rows)
    latest_by_region: dict[str, dict[str, Any]] = {}
    for record in records:
        key = str(record.get("region_normalized") or record.get("region"))
        latest_by_region.setdefault(key, record)
    return {"region": normalized_region, "records": records, "latest_by_region": latest_by_region}


def simulate_action(
    action_plan: list[str] | list[dict[str, Any]],
    region: str = "National",
    run_id: str | None = None,
) -> dict[str, Any]:
    from chat_agent.simulation import run_simulation

    return run_simulation(action_plan=action_plan, region=region, run_id=run_id)


def log_decision(
    decision: str,
    *,
    event_type: str = "agent_decision",
    region: str | None = None,
    run_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return log_action(
        event_type,
        payload or {"decision": decision},
        run_id=run_id,
        region=region,
        trace_message=decision,
    )


def generate_signals(db_data: dict[str, Any], time_intent: str = "unspecified") -> dict[str, Any]:
    """Generate signals with time context filtering. Returns dict with selected/discarded/stale."""
    return generate_signals_with_time_context(db_data, time_intent=time_intent)


def compute_risk_signals(regions: list[str] | None = None, time_intent: str = "unspecified") -> dict[str, Any]:
    """Compute risk signals with time-aware filtering."""
    requested_regions = regions or ["Punjab", "Sindh", "KP", "Balochistan"]
    db_data = {"regions": []}

    for region in requested_regions:
        normalized_region = normalize_region(region)
        db_data["regions"].append(
            {
                "region": normalized_region,
                "prices": get_prices(normalized_region, limit=300),
                "disasters": get_disasters(normalized_region, limit=5),
                "weather": get_weather(normalized_region, limit=5),
                "news": get_news([normalized_region, "food", "flood", "inflation", "agriculture"], limit=5),
            }
        )

    return generate_signals(db_data, time_intent=time_intent)


# ============================================================================
# NEW: 3-LAYER REASONING INTEGRATION
# ============================================================================

def get_historical_baseline(region: str = "National") -> dict[str, Any]:
    """
    LAYER 1: Extract historical baseline from CSV data.
    
    Returns long-term patterns, not decision signals.
    CSV is used for context only, never for immediate decisions.
    """
    from chat_agent.reasoning_engine import extract_historical_baseline
    
    normalized_region = normalize_region(region)
    prices = get_prices(normalized_region, limit=500)
    climate = get_climate(normalized_region, limit=200)
    
    return extract_historical_baseline(prices, climate)


def get_live_signals(region: str = "National") -> dict[str, Any]:
    """
    LAYER 2: Fetch live signals from high-priority sources.
    
    Priority:
    1. Apify news (event triggers)
    2. Weather API (real-time conditions)
    3. Disaster reports (impact confirmation)
    
    Returns organized by source and priority.
    """
    from chat_agent.reasoning_engine import organize_live_signals
    
    normalized_region = normalize_region(region)
    apify = get_news([normalized_region, "food", "flood", "drought", "inflation", "supply"], limit=10)
    weather = get_weather(normalized_region, limit=5)
    disasters = get_disasters(normalized_region, limit=5)
    
    return organize_live_signals(apify, weather, disasters)


def compute_reasoning_synthesis(
    query_intent: dict[str, Any],
    region: str = "National",
    time_intent: str = "unspecified"
) -> dict[str, Any]:
    """
    LAYER 3: Full 3-layer reasoning synthesis.
    
    Combines:
    - Historical baseline (context)
    - Live signals (reality)
    - Causal reasoning (explanation)
    - Risk forecast (prediction)
    
    Returns complete reasoning trace for user.
    """
    from chat_agent.reasoning_engine import (
        extract_historical_baseline,
        organize_live_signals,
        compare_live_vs_baseline,
        build_causal_chain,
        detect_contradictions,
        generate_risk_forecast,
        synthesize_reasoning
    )
    
    normalized_region = normalize_region(region)
    
    # Get baseline (historical context)
    baseline = get_historical_baseline(normalized_region)
    
    # Get live signals (current reality)
    live_signals = get_live_signals(normalized_region)
    live_prices = get_prices(normalized_region, limit=100)
    
    # Analyze deviations
    analysis = compare_live_vs_baseline(baseline, live_signals, normalized_region, live_prices)
    
    # Build causal chains
    causal_chain = build_causal_chain(
        query_intent.get("intent", "unspecified"),
        baseline,
        live_signals,
        analysis,
        normalized_region,
        live_prices,
    )
    
    # Detect contradictions
    contradictions = detect_contradictions(baseline, live_signals)
    
    # Generate forecast
    forecast = generate_risk_forecast(causal_chain, baseline, live_signals)
    
    # Synthesize complete reasoning
    reasoning = synthesize_reasoning(
        query_intent,
        baseline,
        live_signals,
        analysis,
        causal_chain,
        contradictions,
        forecast,
        region=normalized_region,
    )
    
    return reasoning


def get_signals_with_reasoning(
    region: str = "National",
    time_intent: str = "unspecified"
) -> dict[str, Any]:
    """
    Enhanced signal generation with causal reasoning.
    
    Returns both traditional signals AND reasoning traces.
    Output includes: historical context, live signals, causal chains, risk forecast.
    """
    # Get legacy signals (backward compatible)
    legacy_signals = compute_risk_signals([region], time_intent)
    
    # Get reasoning synthesis
    query_intent = parse_time_intent(None)
    query_intent["intent"] = time_intent
    reasoning = compute_reasoning_synthesis(query_intent, region, time_intent)
    
    # Merge outputs
    return {
        "selected_signals": legacy_signals.get("selected", []),
        "discarded_signals": legacy_signals.get("discarded", []),
        "stale_signals": legacy_signals.get("stale", []),
        "reasoning_trace": reasoning,
        "historical_baseline": reasoning.get("historical_baseline"),
        "live_signals_summary": reasoning.get("live_signals_summary"),
        "causal_chain": reasoning.get("causal_chain"),
        "risk_forecast": reasoning.get("risk_forecast"),
        "final_reasoning": reasoning.get("final_reasoning"),
        "reasoning_confidence": reasoning.get("reasoning_confidence")
    }
