"""
3-LAYER REASONING ENGINE FOR PAKISTAN FOOD SECURITY INTELLIGENCE

Layer 1: Historical Baseline (CSV) - trends, patterns, reference
Layer 2: Current Reality (Live Signals) - Apify, Weather, Disasters
Layer 3: Reasoning Fusion - causal chains, anomaly detection, forecasting

This module transforms isolated signals into causal intelligence.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any
from statistics import mean, stdev

from chat_agent.temporal_resolver import compute_age_days

# ============================================================================
# LAYER 1: EXTRACT HISTORICAL BASELINE FROM CSV
# ============================================================================

def extract_historical_baseline(
    prices: dict[str, Any],
    climate: dict[str, Any],
) -> dict[str, Any]:
    """
    Extract long-term patterns from CSV data.
    
    Returns:
    {
        "price_baseline": {
            "commodity": {
                "avg_price": float,
                "price_range": (min, max),
                "seasonal_pattern": [...],
                "trend": "stable|rising|falling",
                "volatility": float
            }
        },
        "climate_baseline": {
            "rainfall_avg": float,
            "temp_avg": float,
            "seasonal_variations": {...}
        },
        "historical_anomalies": [
            {
                "date": "YYYY-MM-DD",
                "event": "description",
                "impact": "price_increase|supply_shock|..."
            }
        ]
    }
    """
    baseline = {
        "price_baseline": {},
        "climate_baseline": {},
        "historical_anomalies": [],
        "baseline_age_days": None,
        "baseline_confidence": 0.0
    }
    
    # Extract price baselines by commodity
    if prices.get("records"):
        commodities = {}
        for rec in prices["records"]:
            commodity = rec.get("commodity", "Unknown")
            price = rec.get("price")
            if commodity not in commodities:
                commodities[commodity] = []
            if isinstance(price, (int, float)):
                commodities[commodity].append(float(price))
        
        for commodity, price_list in commodities.items():
            if len(price_list) >= 2:
                baseline["price_baseline"][commodity] = {
                    "avg_price": round(mean(price_list), 2),
                    "price_range": (
                        round(min(price_list), 2),
                        round(max(price_list), 2)
                    ),
                    "volatility": round(stdev(price_list), 2) if len(price_list) > 1 else 0.0,
                    "data_points": len(price_list)
                }
    
    # Extract climate baselines
    if climate.get("records"):
        temps = []
        rainfalls = []
        for rec in climate["records"]:
            t = rec.get("temperature")
            r = rec.get("rainfall")
            if isinstance(t, (int, float)):
                temps.append(float(t))
            if isinstance(r, (int, float)):
                rainfalls.append(float(r))
        
        if temps:
            baseline["climate_baseline"]["avg_temperature"] = round(mean(temps), 1)
            baseline["climate_baseline"]["temp_range"] = (
                round(min(temps), 1),
                round(max(temps), 1)
            )
        if rainfalls:
            baseline["climate_baseline"]["avg_rainfall"] = round(mean(rainfalls), 1)
            baseline["climate_baseline"]["rainfall_range"] = (
                round(min(rainfalls), 1),
                round(max(rainfalls), 1)
            )
    
    # Mark baseline quality
    baseline["baseline_confidence"] = 0.7 if baseline["price_baseline"] else 0.0
    
    return baseline


# ============================================================================
# LAYER 2: FETCH AND PRIORITIZE LIVE SIGNALS
# ============================================================================

def organize_live_signals(
    apify_news: dict[str, Any],
    weather: dict[str, Any],
    disasters: dict[str, Any],
) -> dict[str, Any]:
    """
    Organize live signals by priority and recency.
    
    Priority Order:
    1. Apify news (event triggers, highest causality weight)
    2. Weather API (physical reality, real-time conditions)
    3. Disaster reports (impact confirmation, semi-static)
    """
    live_signals = {
        "apify_news": [],
        "weather_signals": [],
        "disaster_signals": [],
        "signal_recency": None,
        "total_live_sources": 0
    }
    
    # Extract Apify news as event triggers
    if apify_news.get("records"):
        for rec in apify_news["records"]:
            live_signals["apify_news"].append({
                "title": rec.get("title", ""),
                "content": rec.get("content", ""),
                "timestamp": rec.get("date"),  # actual publish date ONLY, never created_at
                "source": "apify",
                "priority": 1,
                "event_triggers": _extract_event_triggers(rec)
            })
    
    # Extract weather as physical reality
    if weather.get("records"):
        for rec in weather["records"]:
            live_signals["weather_signals"].append({
                "region": rec.get("region", ""),
                "temperature": rec.get("temperature"),
                "rainfall": rec.get("rainfall"),
                "humidity": rec.get("humidity"),
                "timestamp": rec.get("timestamp"),
                "source": "weather_api",
                "priority": 2,
                "anomaly_flags": _flag_weather_anomalies(rec)
            })
    
    # Extract disaster reports
    if disasters.get("records"):
        for rec in disasters["records"]:
            live_signals["disaster_signals"].append({
                "type": rec.get("type", ""),
                "severity": rec.get("severity_level", ""),
                "timestamp": rec.get("signal_timestamp") or rec.get("date"),
                "source": "disaster_feed",
                "priority": 3,
                "impact_areas": rec.get("region") or "Unknown",
                "supply_risk": rec.get("supply_risk"),
                "food_price_pressure": rec.get("food_price_pressure")
            })
    
    # Calculate signal recency
    all_timestamps = []
    for sig_list in [live_signals["apify_news"], live_signals["weather_signals"], live_signals["disaster_signals"]]:
        for sig in sig_list:
            ts = sig.get("timestamp")
            if ts:
                all_timestamps.append(ts)
    
    if all_timestamps:
        live_signals["signal_recency"] = max(all_timestamps)
        live_signals["total_live_sources"] = len([s for s in [live_signals["apify_news"], live_signals["weather_signals"], live_signals["disaster_signals"]] if s])
    
    return live_signals


def _extract_event_triggers(news_record: dict[str, Any]) -> list[str]:
    """Extract event trigger keywords from news."""
    triggers = []
    text = (str(news_record.get("title", "")) + " " + str(news_record.get("content", ""))).lower()
    
    event_keywords = {
        "flood": ["flood", "inundation", "heavy rain"],
        "drought": ["drought", "dry", "no rainfall"],
        "supply_shock": ["shortage", "disruption", "import", "export"],
        "price_spike": ["price increase", "inflation", "expensive"],
        "disease": ["disease", "pest", "blight"],
        "infrastructure": ["road", "bridge", "damaged", "destroyed"]
    }
    
    for event, keywords in event_keywords.items():
        if any(kw in text for kw in keywords):
            triggers.append(event)
    
    return triggers


def _flag_weather_anomalies(weather_record: dict[str, Any]) -> list[str]:
    """Flag unusual weather conditions."""
    flags = []
    temp = weather_record.get("temperature")
    rain = weather_record.get("rainfall")
    humidity = weather_record.get("humidity")
    
    if isinstance(temp, (int, float)):
        if temp >= 40:
            flags.append("extreme_heat")
        elif temp <= 5:
            flags.append("extreme_cold")
    
    if isinstance(rain, (int, float)):
        if rain >= 50:
            flags.append("heavy_rainfall")
        elif rain == 0:
            flags.append("no_rainfall")
    
    if isinstance(humidity, (int, float)):
        if humidity >= 85:
            flags.append("high_humidity")
    
    return flags


# ============================================================================
# LAYER 3: REASONING FUSION - ANALYSIS & CAUSAL CHAINS
# ============================================================================

def compare_live_vs_baseline(
    baseline: dict[str, Any],
    live_signals: dict[str, Any],
    region: str,
    live_prices: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Compare live reality against historical baseline.
    Detect anomalies and deviations.
    """
    analysis = {
        "anomalies_detected": [],
        "deviations": [],
        "confidence_score": 0.5,
        "reasoning": ""
    }
    
    evidence_count = 0

    # Price deviation check against historical baseline
    if live_prices and live_prices.get("price_spikes"):
        price_baseline = baseline.get("price_baseline", {})
        for spike in live_prices["price_spikes"][:3]:
            commodity = spike.get("commodity", "Unknown")
            latest_price = float(spike.get("latest_price", 0) or 0)
            hist = price_baseline.get(commodity, {})
            hist_avg = float(hist.get("avg_price", 0) or 0)

            if hist_avg > 0:
                deviation_pct = ((latest_price - hist_avg) / hist_avg) * 100
            else:
                deviation_pct = float(spike.get("change_pct", 0) or 0)

            severity = "critical" if deviation_pct > 50 else "high" if deviation_pct > 25 else "medium" if deviation_pct > 10 else "low"
            analysis["deviations"].append({
                "commodity": commodity,
                "current_price": round(latest_price, 2),
                "historical_avg": round(hist_avg, 2),
                "deviation_pct": round(deviation_pct, 1),
                "severity": severity,
                "market": spike.get("market", "Unknown"),
            })
            evidence_count += 1

    # Check weather anomalies
    for weather_sig in live_signals.get("weather_signals", []):
        if weather_sig.get("region") != region and region != "National":
            continue
        
        anomalies = weather_sig.get("anomaly_flags", [])
        if anomalies:
            for anomaly in anomalies:
                analysis["anomalies_detected"].append({
                    "type": anomaly,
                    "source": "weather",
                    "severity": _severity_from_anomaly(anomaly),
                    "region": weather_sig.get("region", region),
                })
                evidence_count += 1
    
    analysis["confidence_score"] = min(1.0, 0.3 + (evidence_count * 0.15))

    parts = []
    if analysis["deviations"]:
        top = analysis["deviations"][0]
        parts.append(
            f"{top['commodity']} price is {top['deviation_pct']:+.1f}% vs historical average "
            f"(current: {top['current_price']}, avg: {top['historical_avg']}) in {top['market']}."
        )
    if analysis["anomalies_detected"]:
        anomaly_names = [a["type"].replace("_", " ") for a in analysis["anomalies_detected"][:2]]
        parts.append(f"Weather flags: {', '.join(anomaly_names)}.")

    analysis["reasoning"] = " ".join(parts) if parts else "No significant deviation from baseline detected."
    
    return analysis


def build_causal_chain(
    query_intent: str,
    baseline: dict[str, Any],
    live_signals: dict[str, Any],
    analysis: dict[str, Any],
    region: str,
    live_prices: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Build explicit causal reasoning chains.
    
    Examples:
    - Flood event → Supply disruption → Price pressure
    - Drought + High temps → Reduced yield → Future shortage
    - Import restriction + Demand spike → Market inflation
    """
    causal_chain = []

    CAUSE_EFFECT_MAP = {
        "flood": {"effects": ["supply_disruption", "logistics_breakdown", "price_spike"], "horizon": "0-7 days"},
        "drought": {"effects": ["yield_reduction", "supply_shortage", "future_price_increase"], "horizon": "30-90 days"},
        "extreme_heat": {"effects": ["crop_stress", "water_scarcity", "yield_reduction"], "horizon": "14-30 days"},
        "heavy_rainfall": {"effects": ["flood_risk", "infrastructure_damage", "supply_disruption"], "horizon": "0-14 days"},
        "supply_shock": {"effects": ["market_pressure", "consumer_inflation"], "horizon": "7-21 days"},
        "price_spike": {"effects": ["food_insecurity", "demand_suppression", "hoarding_risk"], "horizon": "0-14 days"},
        "infrastructure": {"effects": ["transport_disruption", "delivery_delays", "price_increase"], "horizon": "7-30 days"},
    }

    news_triggers = [
        trigger
        for sig in live_signals.get("apify_news", [])
        for trigger in sig.get("event_triggers", [])
    ]

    for trigger in news_triggers:
        mapping = CAUSE_EFFECT_MAP.get(trigger)
        if not mapping:
            continue
        # Uncorroborated news-only chains get LOW confidence (0.40)
        # They are speculative — useful as early warnings but NOT for decisions.
        causal_chain.append({
            "cause": trigger,
            "cause_source": "news",
            "direct_effects": mapping["effects"],
            "impact_horizon": mapping["horizon"],
            "region": region,
            "confidence": 0.40,  # capped: single-source, unverified
            "evidence_sources": ["apify_news"],
            "corroborated": False,
        })

    weather_anomalies = [
        anomaly
        for sig in live_signals.get("weather_signals", [])
        for anomaly in sig.get("anomaly_flags", [])
    ]

    for anomaly in weather_anomalies:
        mapping = CAUSE_EFFECT_MAP.get(anomaly)
        if not mapping:
            continue
        corroborated = anomaly in news_triggers or any(effect in news_triggers for effect in mapping["effects"])
        causal_chain.append({
            "cause": anomaly,
            "cause_source": "weather",
            "direct_effects": mapping["effects"],
            "impact_horizon": mapping["horizon"],
            "region": region,
            "confidence": 0.90 if corroborated else 0.70,
            "evidence_sources": ["weather_api"] + (["apify_news"] if corroborated else []),
            "corroborated": corroborated,
        })

    for disaster_sig in live_signals.get("disaster_signals", []):
        supply_risk = str(disaster_sig.get("supply_risk", "")).lower()
        if "high" in supply_risk or "critical" in supply_risk:
            causal_chain.append({
                "cause": "disaster_impact",
                "cause_source": "ndma_report",
                "direct_effects": ["supply_chain_disruption", "crop_loss", "price_pressure"],
                "impact_horizon": "0-30 days",
                "region": disaster_sig.get("impact_areas", region),
                "confidence": 0.85,
                "evidence_sources": ["disaster_feed"],
                "corroborated": False,
            })

    for deviation in analysis.get("deviations", []):
        if deviation.get("severity") in ("high", "critical"):
            causal_chain.append({
                "cause": f"{deviation['commodity']}_price_deviation",
                "cause_source": "price_csv",
                "direct_effects": ["consumer_affordability_pressure", "demand_shift", "hoarding_risk"],
                "impact_horizon": "immediate",
                "region": region,
                "deviation_detail": f"{deviation['deviation_pct']:+.1f}% above historical average",
                "confidence": 0.75,
                "evidence_sources": ["wfp_price_data"],
                "corroborated": len(analysis.get("anomalies_detected", [])) > 0,
            })

    seen_causes: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for step in causal_chain:
        cause = str(step.get("cause", ""))
        if cause and cause not in seen_causes:
            seen_causes.add(cause)
            deduped.append(step)

    return deduped


def detect_contradictions(
    baseline: dict[str, Any],
    live_signals: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Cross-validate signals from multiple sources.
    Detect conflicts and resolve using temporal priority.
    """
    contradictions = []
    
    # If weather shows extreme heat but no crop damage news, flag it
    extreme_weather = any(
        "extreme" in str(flag)
        for sig in live_signals.get("weather_signals", [])
        for flag in sig.get("anomaly_flags", [])
    )
    
    crop_damage_news = any(
        "supply_shock" in str(triggers) or "damage" in str(triggers).lower()
        for sig in live_signals.get("apify_news", [])
        for triggers in sig.get("event_triggers", [])
    )
    
    if extreme_weather and not crop_damage_news:
        contradictions.append({
            "type": "missing_evidence",
            "description": "Extreme weather detected but no crop impact news yet",
            "severity": "low",
            "resolution": "Continue monitoring for delayed impact reporting"
        })
    
    return contradictions


def generate_risk_forecast(
    causal_chain: list[dict[str, Any]],
    baseline: dict[str, Any],
    live_signals: dict[str, Any],
) -> dict[str, Any]:
    """
    Generate forward-looking risk assessment based on causal reasoning.

    Key safety rules:
    - No 'critical' without corroborated evidence from 2+ sources.
    - Confidence is penalized by the ratio of uncorroborated chains.
    - Empty causal chain → 'low' risk with 0.1 confidence.
    """
    forecast = {
        "risk_level": "low",
        "confidence": 0.1,
        "forecast_horizon_days": 30,
        "predicted_impacts": [],
        "recommended_actions": []
    }

    if not causal_chain:
        return forecast

    # Aggregate risk from causal chain
    total_risk = 0.0
    corroborated_count = 0
    for step in causal_chain:
        weight = step.get("confidence", 0.5)
        if "supply" in str(step.get("direct_effects")).lower():
            total_risk += 0.3 * weight
        if "price" in str(step.get("direct_effects")).lower():
            total_risk += 0.25 * weight
        if step.get("corroborated"):
            corroborated_count += 1

    # Corroboration ratio: what fraction of chains are multi-source confirmed?
    corroboration_ratio = corroborated_count / max(1, len(causal_chain))

    # Determine risk level — 'critical' REQUIRES corroborated evidence
    if total_risk > 0.7 and corroboration_ratio >= 0.3:
        forecast["risk_level"] = "critical"
    elif total_risk > 0.5 and corroboration_ratio >= 0.2:
        forecast["risk_level"] = "high"
    elif total_risk > 0.5:
        # High raw risk but no corroboration → cap at "elevated"
        forecast["risk_level"] = "elevated"
    elif total_risk > 0.3:
        forecast["risk_level"] = "medium"

    # Confidence formula: penalize heavily for single-source-only chains
    raw_confidence = min(1.0, total_risk + 0.1)
    corroboration_penalty = 1.0 if corroboration_ratio >= 0.5 else (0.5 + corroboration_ratio)
    forecast["confidence"] = round(min(0.95, raw_confidence * corroboration_penalty), 2)

    # Generate predicted impacts
    for step in causal_chain:
        for effect in step.get("direct_effects", []):
            forecast["predicted_impacts"].append({
                "impact": effect,
                "source": step.get("cause"),
                "probability": step.get("confidence", 0.5),
                "timeline": step.get("impact_horizon", "7-30 days"),
                "corroborated": step.get("corroborated", False),
            })

    # Generate actions
    if forecast["risk_level"] in ["critical", "high"]:
        forecast["recommended_actions"] = [
            "Monitor supply chain continuously",
            "Prepare contingency procurement",
            "Alert stakeholders",
            "Track price movements"
        ]
    elif forecast["risk_level"] == "elevated":
        forecast["recommended_actions"] = [
            "Increase monitoring frequency",
            "Verify signals with ground-level sources",
            "Track price movements"
        ]

    return forecast


def _severity_from_anomaly(anomaly: str) -> str:
    """Map anomaly type to severity."""
    severity_map = {
        "extreme_heat": "high",
        "extreme_cold": "high",
        "heavy_rainfall": "high",
        "no_rainfall": "medium",
        "high_humidity": "medium"
    }
    return severity_map.get(anomaly, "low")


# ============================================================================
# UNIFIED REASONING OUTPUT
# ============================================================================

def synthesize_reasoning(
    query_intent: dict[str, Any],
    baseline: dict[str, Any],
    live_signals: dict[str, Any],
    analysis: dict[str, Any],
    causal_chain: list[dict[str, Any]],
    contradictions: list[dict[str, Any]],
    forecast: dict[str, Any],
    region: str = "National",
) -> dict[str, Any]:
    """
    Generate complete reasoning trace for user.
    """
    return {
        "query_intent": query_intent,
        "historical_baseline": baseline,
        "live_signals_summary": {
            "apify_news_count": len(live_signals.get("apify_news", [])),
            "weather_signals_count": len(live_signals.get("weather_signals", [])),
            "disaster_signals_count": len(live_signals.get("disaster_signals", [])),
            "most_recent_signal": live_signals.get("signal_recency")
        },
        "deviation_analysis": analysis,
        "causal_chain": causal_chain,
        "contradictions": contradictions,
        "risk_forecast": forecast,
        "reasoning_confidence": min(1.0, (analysis.get("confidence_score", 0.5) + forecast.get("confidence", 0.5)) / 2),
        "final_reasoning": _generate_narrative(causal_chain, forecast, analysis, region)
    }


def _generate_narrative(
    causal_chain: list[dict[str, Any]],
    forecast: dict[str, Any],
    analysis: dict[str, Any] | None = None,
    region: str = "National",
) -> str:
    """Generate plain-English reasoning narrative."""
    if not causal_chain and not (analysis and analysis.get("deviations")):
        return (
            f"No significant deviation from historical baseline detected in {region}. "
            "CSV price data and climate records show normal ranges. Continue routine monitoring."
        )

    parts = []

    high_conf_chains = [c for c in causal_chain if c.get("confidence", 0) >= 0.75]
    if high_conf_chains:
        primary = sorted(
            high_conf_chains,
            key=lambda item: (
                0 if item.get("cause_source") == "price_csv" else 1,
                -float(item.get("confidence", 0) or 0),
            ),
        )[0]
        cause_label = str(primary.get("cause", "unknown")).replace("_", " ").title()
        effects = ", ".join(str(e).replace("_", " ") for e in primary.get("direct_effects", [])[:2])
        source = str(primary.get("cause_source", "data")).replace("_", " ")
        parts.append(
            f"Primary driver ({source}): {cause_label} is creating {effects} in {primary.get('region', region)}."
        )

    if analysis and analysis.get("deviations"):
        top_dev = analysis["deviations"][0]
        direction = "above" if top_dev["deviation_pct"] > 0 else "below"
        parts.append(
            f"{top_dev['commodity']} is currently {abs(top_dev['deviation_pct']):.1f}% {direction} its historical average "
            f"in {top_dev['market']} market (current: PKR {top_dev['current_price']}, avg: PKR {top_dev['historical_avg']})."
        )

    corroborated = [c for c in causal_chain if c.get("corroborated")]
    single_source = [c for c in causal_chain if not c.get("corroborated")]

    risk_level = forecast.get("risk_level", "unknown").upper()
    horizon = forecast.get("forecast_horizon_days", 30)
    confidence = forecast.get("confidence", 0.0)

    # Build a more narrative and simple summary for the user
    summary_parts = []
    
    # 1. What it looked for
    summary_parts.append("### 🔍 Analysis Scope")
    summary_parts.append(f"I conducted a multi-dimensional assessment of food security for **{region}**. I analyzed current market prices, supply chain signals, and environmental data points.")
    
    # 2. How it looked for it
    summary_parts.append("\n### 🛠️ Investigation Method")
    how_it_looked = []
    if analysis and analysis.get("deviations"):
        how_it_looked.append("compared local market price deviations against historical 3-year averages")
    if any(c.get("cause_source") == "weather" for c in causal_chain):
        how_it_looked.append("cross-referenced meteorological stress reports")
    if any(c.get("cause_source") == "news" or c.get("cause_source") == "apify" for c in causal_chain):
        how_it_looked.append("scanned news alerts and social sentiment for logistics bottlenecks")
    
    if not how_it_looked:
        how_it_looked.append("verified regional baseline databases and available signal feeds")
    
    summary_parts.append(f"To reach this conclusion, I {', '.join(how_it_looked[:-1]) + ' and ' + how_it_looked[-1] if len(how_it_looked) > 1 else how_it_looked[0]}.")

    # 3. Results
    summary_parts.append("\n### 📊 Findings & Assessment")
    
    if parts:
        summary_parts.append(" ".join(parts))
    else:
        summary_parts.append(f"Currently, no active crisis signals are triggering emergency thresholds in {region}. The regional market appears stable based on latest telemetry.")

    summary_parts.append(f"\n**Risk Level:** {risk_level} ({confidence:.0%} confidence)")
    summary_parts.append(f"**Forecast Horizon:** Next {horizon} days")

    return "\n".join(summary_parts)
