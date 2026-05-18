from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data.db"

NEWS_TABLE = "news"
WEATHER_TABLE = "weather"
DISASTERS_TABLE = "disasters"
ACTIONS_LOG_TABLE = "actions_log"
SIMULATION_STATE_TABLE = "simulation_state"

REGION_ALIASES = {
    "national": "National",
    "pakistan": "National",
    "punjab": "Punjab",
    "sindh": "Sindh",
    "balochistan": "Balochistan",
    "balochistan province": "Balochistan",
    "kp": "Khyber Pakhtunkhwa",
    "kpk": "Khyber Pakhtunkhwa",
    "khyber pakhtunkhwa": "Khyber Pakhtunkhwa",
    "khyber-pakhtunkhwa": "Khyber Pakhtunkhwa",
    "north west frontier province": "Khyber Pakhtunkhwa",
    "gilgit baltistan": "Gilgit-Baltistan",
    "gilgit-baltistan": "Gilgit-Baltistan",
    "gb": "Gilgit-Baltistan",
    "islamabad": "Islamabad Capital Territory",
    "islamabad capital territory": "Islamabad Capital Territory",
    "ict": "Islamabad Capital Territory",
    "azad jammu and kashmir": "Azad Jammu and Kashmir",
    "ajk": "Azad Jammu and Kashmir",
}

DISASTER_COLUMNS = [
    "report_status",
    "report_final_date",
    "report_sources",
    "confidence_score",
    "region",
    "region_normalized",
    "signal_timestamp",
    "severity_level",
    "severity_reason",
    "deceased",
    "injured",
    "persons_rescued",
    "houses_partial",
    "houses_full",
    "roads_km",
    "bridges",
    "crop_loss_acres",
    "supply_risk",
    "food_price_pressure",
    "logistics_disruption",
    "relief_camps",
    "persons_in_camps",
    "medical_camps",
    "logistics_status",
    "high_impact_commodities",
    "medium_impact_commodities",
    "low_impact_commodities",
    "created_at",
]


def load_env(env_path: Path | None = None) -> None:
    """Load simple KEY=value pairs from .env without adding another dependency."""
    # Check both chat_agent/.env and parent backend/.env
    paths_to_check = []
    if env_path:
        paths_to_check.append(env_path)
    paths_to_check.append(BASE_DIR / ".env")
    paths_to_check.append(BASE_DIR.parent / ".env")  # backend/.env

    for path in paths_to_check:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def get_env(*names: str) -> str | None:
    load_env()
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_region(region: Any) -> str:
    if region is None:
        return "National"
    text = re.sub(r"\s+", " ", str(region)).strip()
    if not text:
        return "National"
    key = text.casefold().replace(".", "")
    return REGION_ALIASES.get(key, text)


def canonical_regions() -> list[str]:
    return ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan"]


def get_connection(row_factory: bool = True) -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    if row_factory:
        connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA synchronous = NORMAL;")
    return connection


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def ensure_schema() -> None:
    with get_connection() as connection:
        connection.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS {NEWS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                date TEXT,
                source TEXT,
                url TEXT,
                keywords TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(title, source, date)
            );

            CREATE TABLE IF NOT EXISTS {WEATHER_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                region TEXT NOT NULL,
                region_normalized TEXT NOT NULL,
                temperature REAL,
                rainfall REAL,
                humidity REAL,
                timestamp TEXT NOT NULL,
                source TEXT,
                raw_json TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(region_normalized, timestamp)
            );

            CREATE TABLE IF NOT EXISTS {DISASTERS_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_status TEXT,
                report_final_date TEXT,
                report_sources TEXT,
                confidence_score REAL,
                region TEXT,
                region_normalized TEXT,
                signal_timestamp TEXT,
                severity_level TEXT,
                severity_reason TEXT,
                deceased INTEGER,
                injured INTEGER,
                persons_rescued INTEGER,
                houses_partial INTEGER,
                houses_full INTEGER,
                roads_km REAL,
                bridges INTEGER,
                crop_loss_acres REAL,
                supply_risk TEXT,
                food_price_pressure TEXT,
                logistics_disruption TEXT,
                relief_camps INTEGER,
                persons_in_camps INTEGER,
                medical_camps INTEGER,
                logistics_status TEXT,
                high_impact_commodities TEXT,
                medium_impact_commodities TEXT,
                low_impact_commodities TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(region_normalized, signal_timestamp)
            );

            CREATE TABLE IF NOT EXISTS {ACTIONS_LOG_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                event_type TEXT NOT NULL,
                region TEXT,
                trace_message TEXT,
                payload TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS {SIMULATION_STATE_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                region TEXT NOT NULL,
                before_state TEXT NOT NULL,
                after_state TEXT NOT NULL,
                action_chain TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_news_date
                ON {NEWS_TABLE} (date);
            CREATE INDEX IF NOT EXISTS idx_news_source
                ON {NEWS_TABLE} (source);
            CREATE INDEX IF NOT EXISTS idx_weather_region_time
                ON {WEATHER_TABLE} (region_normalized, timestamp);
            CREATE INDEX IF NOT EXISTS idx_disasters_region_time
                ON {DISASTERS_TABLE} (region_normalized, signal_timestamp);
            CREATE INDEX IF NOT EXISTS idx_actions_log_created
                ON {ACTIONS_LOG_TABLE} (created_at);
            """
        )

        if table_exists(connection, "disaster_signals"):
            existing = connection.execute(f"SELECT COUNT(*) FROM {DISASTERS_TABLE}").fetchone()[0]
            if existing == 0:
                column_list = ", ".join(DISASTER_COLUMNS)
                connection.execute(
                    f"""
                    INSERT OR IGNORE INTO {DISASTERS_TABLE} ({column_list})
                    SELECT {column_list}
                    FROM disaster_signals
                    """
                )


def dict_from_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def dicts_from_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict_from_row(row) or {} for row in rows]


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)


def json_loads(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def log_action(
    event_type: str,
    payload: Any,
    *,
    run_id: str | None = None,
    region: str | None = None,
    trace_message: str | None = None,
) -> dict[str, Any]:
    ensure_schema()
    created_at = utc_now_iso()
    normalized_region = normalize_region(region) if region else None
    with get_connection() as connection:
        cursor = connection.execute(
            f"""
            INSERT INTO {ACTIONS_LOG_TABLE}
                (run_id, event_type, region, trace_message, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, event_type, normalized_region, trace_message, json_dumps(payload), created_at),
        )
        log_id = int(cursor.lastrowid)
    return {
        "id": log_id,
        "run_id": run_id,
        "event_type": event_type,
        "region": normalized_region,
        "trace_message": trace_message,
        "payload": payload,
        "created_at": created_at,
    }


def fetch_action_logs(limit: int = 50) -> list[dict[str, Any]]:
    ensure_schema()
    bounded_limit = max(1, min(int(limit), 500))
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT id, run_id, event_type, region, trace_message, payload, created_at
            FROM {ACTIONS_LOG_TABLE}
            ORDER BY id DESC
            LIMIT ?
            """,
            (bounded_limit,),
        ).fetchall()
    logs = []
    for row in rows:
        item = dict_from_row(row) or {}
        item["payload"] = json_loads(item.get("payload"))
        logs.append(item)
    return logs
