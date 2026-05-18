from __future__ import annotations

from typing import Any
from uuid import uuid4

from chat_agent.db import SIMULATION_STATE_TABLE, ensure_schema, get_connection, json_dumps, log_action, normalize_region, utc_now_iso
from chat_agent.tools import get_disasters, get_prices, get_weather


def _risk_level_score(value: Any) -> float:
    text = str(value or "").casefold()
    if "critical" in text:
        return 90.0
    if "high" in text:
        return 72.0
    if "medium" in text:
        return 48.0
    if "low" in text:
        return 22.0
    return 0.0


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_action_plan(action_plan: list[str] | list[dict[str, Any]] | str) -> list[str]:
    if isinstance(action_plan, str):
        return [action_plan]
    normalized = []
    for item in action_plan:
        if isinstance(item, dict):
            text = item.get("action") or item.get("step") or item.get("description") or json_dumps(item)
        else:
            text = str(item)
        text = " ".join(text.split())
        if text:
            normalized.append(text)
    return normalized


def build_current_state(region: str = "National") -> dict[str, Any]:
    normalized_region = normalize_region(region)
    prices = get_prices(normalized_region, limit=400)
    disasters = get_disasters(normalized_region, limit=5)
    weather = get_weather(normalized_region, limit=5)

    top_spike = prices["price_spikes"][0] if prices["price_spikes"] else None
    price_pressure = min(100.0, 35.0 + float(top_spike["change_pct"])) if top_spike else 25.0

    disaster_scores = []
    for impact in disasters["active_impacts"]:
        disaster_scores.extend(
            [
                _risk_level_score(impact.get("supply_risk")),
                _risk_level_score(impact.get("food_price_pressure")),
                _risk_level_score(impact.get("logistics_disruption")),
            ]
        )
        crop_loss = _num(impact.get("crop_loss_acres")) or 0.0
        if crop_loss:
            disaster_scores.append(min(100.0, 45.0 + crop_loss / 100000.0))
    disaster_pressure = max(disaster_scores) if disaster_scores else 20.0

    latest_weather = next(iter(weather["latest_by_region"].values()), None)
    weather_pressure = 0.0
    if latest_weather:
        temperature = _num(latest_weather.get("temperature"))
        rainfall = _num(latest_weather.get("rainfall"))
        humidity = _num(latest_weather.get("humidity"))
        if temperature is not None and temperature >= 40:
            weather_pressure += 30.0
        if rainfall is not None and rainfall >= 20:
            weather_pressure += 30.0
        if humidity is not None and humidity >= 85:
            weather_pressure += 10.0

    supply_risk = min(100.0, max(disaster_pressure, weather_pressure, 20.0))
    logistics_risk = min(100.0, max(disaster_pressure * 0.8, weather_pressure * 0.7, 15.0))
    supply_index = max(0.0, 100.0 - (supply_risk * 0.45))
    affordability_index = max(0.0, 100.0 - (price_pressure * 0.5))

    return {
        "region": normalized_region,
        "price_index": round(100.0 + price_pressure * 0.35, 2),
        "supply_index": round(supply_index, 2),
        "affordability_index": round(affordability_index, 2),
        "logistics_risk": round(logistics_risk, 2),
        "supply_risk": round(supply_risk, 2),
        "top_price_spike": top_spike,
        "weather_snapshot": latest_weather,
        "disaster_count": len(disasters["records"]),
    }


def _apply_action(after: dict[str, Any], action: str) -> dict[str, Any]:
    text = action.casefold()
    impact = {
        "action": action,
        "price_index_delta": 0.0,
        "supply_index_delta": 0.0,
        "affordability_index_delta": 0.0,
        "logistics_risk_delta": 0.0,
    }

    if any(term in text for term in ["stock", "reserve", "release", "ration"]):
        impact["price_index_delta"] -= 8.0
        impact["supply_index_delta"] += 6.0
        impact["affordability_index_delta"] += 5.0
    if any(term in text for term in ["distribution", "distribute", "relief logistics", "emergency food"]):
        impact["price_index_delta"] -= 4.0
        impact["supply_index_delta"] += 9.0
        impact["affordability_index_delta"] += 7.0
        impact["logistics_risk_delta"] -= 10.0
    if any(term in text for term in ["import", "procure", "purchase"]):
        impact["price_index_delta"] -= 10.0
        impact["supply_index_delta"] += 8.0
    if any(term in text for term in ["transport", "logistics", "route", "bridge", "warehouse"]):
        impact["logistics_risk_delta"] -= 12.0
        impact["supply_index_delta"] += 7.0
    if any(term in text for term in ["subsidy", "cash", "voucher", "support"]):
        impact["affordability_index_delta"] += 12.0
        impact["price_index_delta"] -= 2.0
    if any(term in text for term in ["fertilizer", "seed", "irrigation", "extension", "farmer"]):
        impact["supply_index_delta"] += 5.0
    if any(term in text for term in ["monitor", "hoarding", "enforcement", "market"]):
        impact["price_index_delta"] -= 6.0
    if any(term in text for term in ["warning", "evacuation", "relief", "camp"]):
        impact["logistics_risk_delta"] -= 5.0
        impact["supply_index_delta"] += 3.0

    after["price_index"] = round(max(0.0, after["price_index"] + impact["price_index_delta"]), 2)
    after["supply_index"] = round(min(100.0, max(0.0, after["supply_index"] + impact["supply_index_delta"])), 2)
    after["affordability_index"] = round(
        min(100.0, max(0.0, after["affordability_index"] + impact["affordability_index_delta"])),
        2,
    )
    after["logistics_risk"] = round(min(100.0, max(0.0, after["logistics_risk"] + impact["logistics_risk_delta"])), 2)
    after["supply_risk"] = round(min(100.0, max(0.0, after["supply_risk"] - impact["supply_index_delta"] * 0.6)), 2)
    return impact


def run_simulation(
    action_plan: list[str] | list[dict[str, Any]] | str,
    *,
    region: str = "National",
    run_id: str | None = None,
) -> dict[str, Any]:
    ensure_schema()
    resolved_run_id = run_id or str(uuid4())
    normalized_region = normalize_region(region)
    actions = _normalize_action_plan(action_plan)
    before = build_current_state(normalized_region)

    if not actions:
        result = {
            "before": before,
            "after": dict(before),
            "step_impacts": [],
            "run_id": resolved_run_id,
        }
        with get_connection() as connection:
            connection.execute(
                f"""
                INSERT INTO {SIMULATION_STATE_TABLE}
                    (run_id, region, before_state, after_state, action_chain, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    resolved_run_id,
                    normalized_region,
                    json_dumps(before),
                    json_dumps(before),
                    json_dumps(actions),
                    utc_now_iso(),
                ),
            )
        log_action(
            "simulation",
            result,
            run_id=resolved_run_id,
            region=normalized_region,
            trace_message="Simulation produced no-op before/after state",
        )
        return result

    after = dict(before)
    after.pop("top_price_spike", None)
    after.pop("weather_snapshot", None)
    after["intervention_count"] = len(actions)

    step_impacts = [_apply_action(after, action) for action in actions]
    after["price_index_delta"] = round(after["price_index"] - before["price_index"], 2)
    after["supply_index_delta"] = round(after["supply_index"] - before["supply_index"], 2)
    after["affordability_index_delta"] = round(after["affordability_index"] - before["affordability_index"], 2)
    after["logistics_risk_delta"] = round(after["logistics_risk"] - before["logistics_risk"], 2)

    result = {
        "before": before,
        "after": after,
        "step_impacts": step_impacts,
        "run_id": resolved_run_id,
    }

    with get_connection() as connection:
        connection.execute(
            f"""
            INSERT INTO {SIMULATION_STATE_TABLE}
                (run_id, region, before_state, after_state, action_chain, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_run_id,
                normalized_region,
                json_dumps(before),
                json_dumps(after),
                json_dumps(actions),
                utc_now_iso(),
            ),
        )
    log_action(
        "simulation",
        result,
        run_id=resolved_run_id,
        region=normalized_region,
        trace_message="Simulation produced before/after intervention impact",
    )
    return result
