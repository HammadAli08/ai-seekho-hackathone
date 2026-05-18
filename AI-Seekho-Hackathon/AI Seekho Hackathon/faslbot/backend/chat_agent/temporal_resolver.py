"""
Temporal intelligence layer for Pakistan food-security agent.
Handles time intent classification, recency validation, and time-filtered data fetching.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

# Time intent patterns
TIME_PATTERNS: dict[str, list[str]] = {
    "real_time": [
        r"\b(now|today|current|live|immediate|active)\b",
        r"\b(right\s+now|as\s+of)\b",
        r"\b(this\s+moment)\b",
    ],
    "recent": [
        r"\b(recent|lately|latest|fresh)\b",
        r"\b(last\s+(\d+\s+)?(days?|weeks?|hours?))\b",
        r"\b(past\s+(\d+\s+)?(days?|weeks?|months?))\b",
        r"\b(within\s+(\d+\s+)?(days?|week|month))\b",
        r"\b(this\s+(week|month))\b",
    ],
    "historical": [
        r"\b(historical|past|previous|before|ago)\b",
        r"\b((\d+\s+)?(months?|years?)\s+ago)\b",
        r"\b(last\s+(year|season))\b",
        r"\b(2024|2023|2022|2021)\b",
        r"\b(trend|average|baseline)\b",
    ],
}

# Time intent confidence thresholds
REAL_TIME_DAYS = 7
RECENT_DAYS = 30
HISTORICAL_DAYS = 365 * 2


def parse_time_intent(user_query: str | None) -> dict[str, Any]:
    """
    Parse user query to extract time intent.
    Returns:
    {
        "intent": "real_time" | "recent" | "historical" | "unspecified",
        "confidence": 0..1,
        "max_age_days": int,
        "keywords": [matched patterns],
        "query": original query
    }
    """
    if not user_query:
        return {
            "intent": "unspecified",
            "confidence": 0.0,
            "max_age_days": None,
            "keywords": [],
            "query": None,
        }

    query_lower = str(user_query).casefold()
    scores: dict[str, float] = {"real_time": 0.0, "recent": 0.0, "historical": 0.0}
    matched_keywords = []

    for intent_type, patterns in TIME_PATTERNS.items():
        for pattern in patterns:
            matches = re.findall(pattern, query_lower)
            if matches:
                scores[intent_type] += len(matches) * 0.3
                matched_keywords.extend([m[0] if isinstance(m, tuple) else m for m in matches])

    # Normalize scores
    total = sum(scores.values())
    if total == 0:
        intent = "unspecified"
        confidence = 0.0
        max_age_days = None
    else:
        for key in scores:
            scores[key] /= total
        intent = max(scores.keys(), key=lambda k: scores[k])
        confidence = min(1.0, scores[intent])

        if intent == "real_time":
            max_age_days = REAL_TIME_DAYS
        elif intent == "recent":
            max_age_days = RECENT_DAYS
        else:
            max_age_days = HISTORICAL_DAYS

    return {
        "intent": intent,
        "confidence": round(confidence, 3),
        "max_age_days": max_age_days,
        "keywords": list(set(matched_keywords)),
        "query": user_query,
    }


def parse_timestamp(timestamp_str: str | None) -> datetime | None:
    """Parse ISO/date string to datetime."""
    if not timestamp_str:
        return None
    try:
        ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return ts
    except (ValueError, AttributeError):
        try:
            ts = datetime.strptime(timestamp_str[:10], "%Y-%m-%d")
            return ts.replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError):
            return None


def compute_age_days(timestamp_str: str | None) -> int | None:
    """Compute age of data in days."""
    ts = parse_timestamp(timestamp_str)
    if not ts:
        return None
    now = datetime.now(timezone.utc)
    # ensure both are tz-aware
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = now - ts
    return max(0, int(delta.total_seconds() / 86400.0))


def is_data_valid_for_intent(timestamp_str: str | None, time_intent: str) -> bool:
    """
    Check if data timestamp is acceptable for the given time intent.
    Returns True if data is fresh enough for the intent; False otherwise.
    """
    age = compute_age_days(timestamp_str)
    if age is None:
        # Unknown age is treated as suspicious
        return False

    if time_intent == "real_time":
        return age <= REAL_TIME_DAYS
    if time_intent == "recent":
        return age <= RECENT_DAYS
    if time_intent == "historical":
        return age <= HISTORICAL_DAYS
    # unspecified: accept anything that exists
    return True


def filter_signals_by_time(
    signals: list[dict[str, Any]], time_intent: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Filter signals by time intent.
    Returns (valid_signals, stale_signals).

    IMPORTANT: Uses actual publication date only, never created_at (scrape time).
    """
    valid = []
    stale = []

    for sig in signals:
        # Extract timestamp — ONLY real dates, never created_at (scrape time)
        ts = sig.get("date") or sig.get("timestamp")
        if not ts and isinstance(sig.get("evidence"), dict):
            ts = (
                sig["evidence"].get("date")
                or sig["evidence"].get("signal_timestamp")
                or sig["evidence"].get("timestamp")
            )
        if not ts and isinstance(sig.get("evidence"), list) and sig["evidence"]:
            for ev in sig["evidence"]:
                if isinstance(ev, dict) and ev.get("date"):
                    ts = ev["date"]
                    break

        if is_data_valid_for_intent(ts, time_intent):
            valid.append(sig)
        else:
            stale.append(sig)

    return valid, stale


def create_stale_data_warning(
    discarded_count: int, time_intent: str, max_age_days: int | None
) -> str:
    """Create a clear warning message for stale data."""
    if time_intent == "real_time":
        return f"{discarded_count} signal(s) were older than {max_age_days} days and discarded as stale for real-time query."
    if time_intent == "recent":
        return f"{discarded_count} signal(s) were older than {max_age_days} days and discarded as stale for recent-data query."
    return f"{discarded_count} signal(s) were discarded due to insufficient recency."


def build_time_validated_query(
    base_keywords: list[str], location: str | None = None, time_intent: str = "unspecified"
) -> str:
    """
    Build an Apify query with time context.
    Useful for Apify news scraping to include temporal urgency.
    """
    time_qualifiers = {
        "real_time": "today OR now OR latest OR current",
        "recent": "recent OR this week OR this month OR latest",
        "historical": "trend OR baseline OR average",
        "unspecified": "",
    }

    qualifier = time_qualifiers.get(time_intent, "")
    location_part = f"{location} " if location else ""
    keywords_part = " OR ".join(base_keywords) if base_keywords else ""

    if qualifier:
        return f"{location_part}({keywords_part}) AND ({qualifier})"
    return f"{location_part}{keywords_part}"


def compute_recency_score_v2(timestamp_str: str | None, time_intent: str = "unspecified") -> float:
    """
    Compute recency score (0..1) with emphasis on time intent matching.
    More aggressive penalty for stale data in real_time queries.
    """
    age = compute_age_days(timestamp_str)
    if age is None:
        return 0.0

    if time_intent == "real_time":
        # 0–7 days: 1.0 down to 0.5
        if age <= 7:
            return 1.0 - (age / 14.0)
        # 8–30 days: 0.5 down to 0.1
        if age <= 30:
            return 0.5 - ((age - 7) / 46.0)
        # >30 days: 0.1 down to 0.0
        return max(0.0, 0.1 - ((age - 30) / 300.0))

    if time_intent == "recent":
        # 0–30 days: 1.0 down to 0.6
        if age <= 30:
            return 1.0 - (age / 50.0)
        # 31–90 days: 0.6 down to 0.2
        if age <= 90:
            return 0.6 - ((age - 30) / 100.0)
        # >90 days: 0.2 down to 0.0
        return max(0.0, 0.2 - ((age - 90) / 500.0))

    # historical or unspecified: gentler decay
    if age <= 365 * 2:
        return 1.0 - (age / (365 * 4))
    return max(0.0, 0.25 - ((age - 365 * 2) / (365 * 10)))


def validate_query_time_match(
    resolved_region: dict[str, Any], time_intent: dict[str, Any]
) -> dict[str, Any]:
    """
    Build a summary of the query's geo-temporal context.
    Used by agent for decision making.
    """
    return {
        "location": resolved_region.get("input"),
        "province": resolved_region.get("province"),
        "district": resolved_region.get("district"),
        "geo_confidence": resolved_region.get("confidence", 0.0),
        "time_intent": time_intent.get("intent"),
        "time_confidence": time_intent.get("confidence", 0.0),
        "max_age_days": time_intent.get("max_age_days"),
        "combined_confidence": round(
            (resolved_region.get("confidence", 0.0) + time_intent.get("confidence", 0.0)) / 2.0, 3
        ),
    }
