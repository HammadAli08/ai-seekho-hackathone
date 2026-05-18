from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from chat_agent.db import WEATHER_TABLE, ensure_schema, get_connection, get_env, json_dumps, log_action, normalize_region, utc_now_iso
from chat_agent.geo_resolver import resolve_region as geo_resolve

REGION_LOCATIONS = {
    "Punjab": "Lahore, Pakistan",
    "Sindh": "Karachi, Pakistan",
    "Khyber Pakhtunkhwa": "Peshawar, Pakistan",
    "KP": "Peshawar, Pakistan",
    "Balochistan": "Quetta, Pakistan",
    "Islamabad Capital Territory": "Islamabad, Pakistan",
    "Gilgit-Baltistan": "Gilgit, Pakistan",
    "Azad Jammu and Kashmir": "Muzaffarabad, Pakistan",
    "National": "Islamabad, Pakistan",
}


def _timestamp_from_weather(current: dict[str, Any]) -> str:
    epoch = current.get("last_updated_epoch")
    if isinstance(epoch, (int, float)):
        return datetime.fromtimestamp(float(epoch), timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    text = current.get("last_updated")
    if isinstance(text, str) and text.strip():
        try:
            return datetime.fromisoformat(text.strip()).replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            return text.strip()
    return utc_now_iso()


def _weather_api_url(location: str, api_key: str) -> str:
    query = urllib.parse.urlencode({"key": api_key, "q": location, "aqi": "no"})
    return f"https://api.weatherapi.com/v1/current.json?{query}"


def fetch_weather_for_region(region: str) -> dict[str, Any]:
    api_key = get_env("WEATHER_API_KEY", "weather_api_key")
    if not api_key:
        raise RuntimeError("WEATHER_API_KEY/weather_api_key is missing")

    # Resolve district-level queries to their province for weather API
    normalized_region_check = normalize_region(region)
    VALID_REGIONS = {"Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan",
                     "National", "Islamabad Capital Territory", "Gilgit-Baltistan",
                     "Azad Jammu and Kashmir"}
    if normalized_region_check not in VALID_REGIONS:
        # Try to resolve district to province
        resolved = geo_resolve(region)
        if resolved.get("resolved") and resolved.get("province"):
            normalized_region_check = resolved["province"]
        else:
            # Fall back to using the location name directly for weather API
            normalized_region_check = normalized_region_check or "National"

    normalized_region = normalized_region_check
    location = REGION_LOCATIONS.get(region) or REGION_LOCATIONS.get(normalized_region) or f"{region}, Pakistan"
    request = urllib.request.Request(_weather_api_url(location, api_key), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Weather API failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Weather API request failed: {exc.reason}") from exc

    current = payload.get("current") or {}
    return {
        "region": region,
        "region_normalized": normalized_region,
        "temperature": current.get("temp_c"),
        "rainfall": current.get("precip_mm"),
        "humidity": current.get("humidity"),
        "timestamp": _timestamp_from_weather(current),
        "source": "weatherapi.com",
        "raw_json": json_dumps(payload),
        "created_at": utc_now_iso(),
    }


def store_weather(rows: list[dict[str, Any]]) -> int:
    ensure_schema()
    if not rows:
        return 0
    with get_connection() as connection:
        cursor = connection.executemany(
            f"""
            INSERT OR REPLACE INTO {WEATHER_TABLE}
                (
                    region, region_normalized, temperature, rainfall, humidity,
                    timestamp, source, raw_json, created_at
                )
            VALUES
                (
                    :region, :region_normalized, :temperature, :rainfall, :humidity,
                    :timestamp, :source, :raw_json, :created_at
                )
            """,
            rows,
        )
        return int(cursor.rowcount if cursor.rowcount is not None else 0)


def ingest_weather(
    *,
    regions: list[str] | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    VALID_REGIONS = {"Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan",
                     "National", "Islamabad Capital Territory", "KP",
                     "Gilgit-Baltistan", "Azad Jammu and Kashmir"}
    requested_regions_raw = regions or ["Punjab", "Sindh", "KP", "Balochistan"]
    # Resolve district names to provinces for weather API compatibility
    requested_regions: list[str] = []
    seen: set[str] = set()
    for r in requested_regions_raw:
        nr = normalize_region(r)
        if nr in VALID_REGIONS or r in VALID_REGIONS:
            if nr not in seen:
                requested_regions.append(r)
                seen.add(nr)
        else:
            resolved = geo_resolve(r)
            prov = resolved.get("province") if resolved.get("resolved") else None
            if prov and prov not in seen:
                requested_regions.append(prov)
                seen.add(prov)
    rows = [fetch_weather_for_region(region) for region in requested_regions]
    inserted = store_weather(rows)
    result = {
        "source": "weatherapi.com",
        "regions": [row["region_normalized"] for row in rows],
        "fetched": len(rows),
        "inserted": inserted,
    }
    log_action("weather_ingestion", result, run_id=run_id, trace_message="Weather ingestion completed")
    return result


if __name__ == "__main__":
    print(json_dumps(ingest_weather()))
