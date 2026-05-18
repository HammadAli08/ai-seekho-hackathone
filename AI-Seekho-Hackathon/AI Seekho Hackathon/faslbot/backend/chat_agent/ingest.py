from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from dateutil import parser as date_parser

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "data.db"

CLIMATE_TABLE = "climate"
PRICES_TABLE = "prices"
GRAIN_SIGNALS_TABLE = "grain_signals"
SYSTEM_METRICS_TABLE = "system_metrics"
GRAIN_INSIGHTS_TABLE = "grain_insights"
DISASTER_SIGNALS_TABLE = "disaster_signals"
CONTRADICTIONS_TABLE = "contradictions"

TABLE_ORDER = [
    CLIMATE_TABLE,
    PRICES_TABLE,
    GRAIN_SIGNALS_TABLE,
    SYSTEM_METRICS_TABLE,
    GRAIN_INSIGHTS_TABLE,
    DISASTER_SIGNALS_TABLE,
    CONTRADICTIONS_TABLE,
]

MONTH_LOOKUP = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}

REGION_ALIASES = {
    "national": "National",
    "punjab": "Punjab",
    "sindh": "Sindh",
    "balochistan": "Balochistan",
    "balochistan province": "Balochistan",
    "kp": "Khyber Pakhtunkhwa",
    "kpk": "Khyber Pakhtunkhwa",
    "khyber pakhtunkhwa": "Khyber Pakhtunkhwa",
    "north west frontier province": "Khyber Pakhtunkhwa",
    "gilgit baltistan": "Gilgit-Baltistan",
    "gilgit-baltistan": "Gilgit-Baltistan",
    "gb": "Gilgit-Baltistan",
    "islamabad": "Islamabad Capital Territory",
    "islamabad capital territory": "Islamabad Capital Territory",
    "ict": "Islamabad Capital Territory",
    "azad jammu and kashmir": "Azad Jammu and Kashmir",
    "ajk": "Azad Jammu and Kashmir",
    "federal": "Federal",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def strip_citations(value: str) -> str:
    return normalize_whitespace(re.sub(r"\s*\[cite:[^\]]+\]", "", value))


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return strip_citations(text)


def normalize_region(region: Any) -> str | None:
    cleaned = clean_text(region)
    if cleaned is None:
        return None

    key = cleaned.casefold().replace(".", "")
    return REGION_ALIASES.get(key, cleaned)


def parse_date_to_iso(value: Any) -> str | None:
    cleaned = clean_text(value)
    if cleaned is None:
        return None
    return date_parser.parse(cleaned).date().isoformat()


def parse_time_period(period: str | None) -> tuple[int | None, int | None]:
    if not period:
        return None, None

    match = re.fullmatch(r"\s*(\d{4})\s*/\s*(\d{4})\s*", period)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def resolve_data_file(*candidate_names: str) -> Path:
    for name in candidate_names:
        path = DATA_DIR / name
        if path.exists():
            return path
    candidates = ", ".join(candidate_names)
    raise FileNotFoundError(f"Could not locate any of: {candidates}")


def normalize_column_name(column_name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", column_name.casefold()).strip("_")
    return cleaned


def recreate_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        f"""
        DROP TABLE IF EXISTS {CLIMATE_TABLE};
        DROP TABLE IF EXISTS {PRICES_TABLE};
        DROP TABLE IF EXISTS {GRAIN_SIGNALS_TABLE};
        DROP TABLE IF EXISTS {SYSTEM_METRICS_TABLE};
        DROP TABLE IF EXISTS {GRAIN_INSIGHTS_TABLE};
        DROP TABLE IF EXISTS {DISASTER_SIGNALS_TABLE};
        DROP TABLE IF EXISTS {CONTRADICTIONS_TABLE};

        CREATE TABLE {CLIMATE_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            metric TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER,
            observed_at TEXT NOT NULL,
            value REAL NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(metric, year, month)
        );

        CREATE TABLE {PRICES_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            cmname TEXT NOT NULL,
            price REAL,
            currency TEXT,
            admname TEXT,
            admname_normalized TEXT,
            mktname TEXT,
            category TEXT,
            category_normalized TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(date, cmname, admname, mktname)
        );

        CREATE TABLE {GRAIN_SIGNALS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            time_period TEXT,
            time_period_start_year INTEGER,
            time_period_end_year INTEGER,
            baseline_comparison TEXT,
            baseline_start_year INTEGER,
            baseline_end_year INTEGER,
            region TEXT,
            region_normalized TEXT,
            commodity TEXT,
            metric TEXT,
            value REAL,
            unit TEXT,
            trend_percentage REAL,
            confidence REAL,
            created_at TEXT NOT NULL,
            UNIQUE(source, time_period, region_normalized, commodity, metric)
        );

        CREATE TABLE {SYSTEM_METRICS_TABLE} (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            source TEXT NOT NULL,
            time_period TEXT,
            time_period_start_year INTEGER,
            time_period_end_year INTEGER,
            baseline_comparison TEXT,
            baseline_start_year INTEGER,
            baseline_end_year INTEGER,
            import_requirement_ratio_wheat REAL,
            export_surplus_ratio_rice REAL,
            buffer_stock_index_wheat REAL,
            raw_risk_indicator_count INTEGER NOT NULL DEFAULT 0,
            risk_overview TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE {GRAIN_INSIGHTS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            time_period TEXT,
            insight_order INTEGER NOT NULL,
            insight TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(source, time_period, insight_order)
        );

        CREATE TABLE {DISASTER_SIGNALS_TABLE} (
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

        CREATE TABLE {CONTRADICTIONS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_final_date TEXT,
            issue TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(report_final_date, issue)
        );

        CREATE INDEX idx_climate_metric_period
            ON {CLIMATE_TABLE} (metric, year, month);

        CREATE INDEX idx_prices_region_item_date
            ON {PRICES_TABLE} (admname_normalized, cmname, date);

        CREATE INDEX idx_grain_region_metric
            ON {GRAIN_SIGNALS_TABLE} (region_normalized, commodity, metric);

        CREATE INDEX idx_disaster_region_date
            ON {DISASTER_SIGNALS_TABLE} (region_normalized, signal_timestamp);
        """
    )


def load_climate_frame(path: Path, metric: str, created_at: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = frame.rename(columns={column: normalize_column_name(column) for column in frame.columns})

    value_columns = [column for column in frame.columns if column not in {"year", "month"}]
    if len(value_columns) != 1:
        raise ValueError(f"Expected exactly one value column in {path.name}, found {value_columns}")

    value_column = value_columns[0]
    if "month" in frame.columns:
        frame["month"] = frame["month"].astype(str).str.strip()
        frame["month"] = frame["month"].replace({"nan": pd.NA})
        frame["month"] = frame["month"].map(lambda value: MONTH_LOOKUP.get(str(value).casefold()) if pd.notna(value) else pd.NA)
    else:
        frame["month"] = pd.NA

    frame["year"] = pd.to_numeric(frame["year"], errors="coerce").astype("Int64")
    frame["value"] = pd.to_numeric(frame[value_column], errors="coerce")
    frame = frame.dropna(subset=["year", "value"])

    frame["year"] = frame["year"].astype(int)
    frame["month"] = frame["month"].astype("Int64")
    frame["observed_at"] = frame.apply(
        lambda row: (
            f"{int(row['year']):04d}-{int(row['month']):02d}-01"
            if pd.notna(row["month"])
            else f"{int(row['year']):04d}-01-01"
        ),
        axis=1,
    )
    frame["source_file"] = path.name
    frame["metric"] = metric
    frame["created_at"] = created_at

    return frame[["source_file", "metric", "year", "month", "observed_at", "value", "created_at"]]


def ingest_climate(connection: sqlite3.Connection, created_at: str) -> int:
    rainfall_path = resolve_data_file("rainfall_1901_2016_pak.csv")
    temperature_path = resolve_data_file(
        "temperature_1901_2016_pakistan.csv",
        "tempreture_1901_2016_pakistan.csv",
    )

    climate_frame = pd.concat(
        [
            load_climate_frame(rainfall_path, "rainfall_mm", created_at),
            load_climate_frame(temperature_path, "temp_celsius", created_at),
        ],
        ignore_index=True,
    )
    climate_frame.to_sql(CLIMATE_TABLE, connection, if_exists="append", index=False)
    return int(len(climate_frame))


def ingest_prices(connection: sqlite3.Connection, created_at: str) -> int:
    prices_path = resolve_data_file("wfp_food_prices_pakistan.csv")
    raw_frame = pd.read_csv(prices_path, skiprows=1)
    frame = raw_frame.rename(
        columns={
            "#date": "date",
            "#item+name": "cmname",
            "#value": "price",
            "#currency": "currency",
            "#adm1+name": "admname",
            "#name+market": "mktname",
            "#item+type": "category",
        }
    )

    frame = frame[["date", "cmname", "price", "currency", "admname", "mktname", "category"]].copy()
    frame["date"] = frame["date"].map(parse_date_to_iso)
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame["cmname"] = frame["cmname"].map(clean_text)
    frame["currency"] = frame["currency"].map(clean_text)
    frame["admname"] = frame["admname"].map(clean_text)
    frame["mktname"] = frame["mktname"].map(clean_text)
    frame["category"] = frame["category"].map(clean_text)
    frame["admname_normalized"] = frame["admname"].map(normalize_region)
    frame["category_normalized"] = frame["category"].str.casefold()
    frame["created_at"] = created_at
    frame = frame.dropna(subset=["date", "cmname"])

    frame.to_sql(PRICES_TABLE, connection, if_exists="append", index=False)
    return int(len(frame))


def load_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def ingest_grain_report(connection: sqlite3.Connection, created_at: str) -> tuple[int, int, int]:
    report_path = resolve_data_file("pakistan_grain_and_feed_report.json")
    report = load_json_file(report_path)

    source = clean_text(report.get("source"))
    time_period = clean_text(report.get("time_period"))
    baseline_comparison = clean_text(report.get("baseline_comparison"))
    period_start_year, period_end_year = parse_time_period(time_period)
    baseline_start_year, baseline_end_year = parse_time_period(baseline_comparison)

    grain_rows = []
    for signal in report.get("agricultural_signals", []):
        grain_rows.append(
            {
                "source": source,
                "time_period": time_period,
                "time_period_start_year": period_start_year,
                "time_period_end_year": period_end_year,
                "baseline_comparison": baseline_comparison,
                "baseline_start_year": baseline_start_year,
                "baseline_end_year": baseline_end_year,
                "region": clean_text(signal.get("region")),
                "region_normalized": normalize_region(signal.get("region")),
                "commodity": clean_text(signal.get("commodity")),
                "metric": clean_text(signal.get("metric")),
                "value": signal.get("value"),
                "unit": clean_text(signal.get("unit")),
                "trend_percentage": signal.get("trend_percentage"),
                "confidence": signal.get("confidence"),
                "created_at": created_at,
            }
        )

    connection.executemany(
        f"""
        INSERT INTO {GRAIN_SIGNALS_TABLE} (
            source, time_period, time_period_start_year, time_period_end_year,
            baseline_comparison, baseline_start_year, baseline_end_year,
            region, region_normalized, commodity, metric, value, unit,
            trend_percentage, confidence, created_at
        )
        VALUES (
            :source, :time_period, :time_period_start_year, :time_period_end_year,
            :baseline_comparison, :baseline_start_year, :baseline_end_year,
            :region, :region_normalized, :commodity, :metric, :value, :unit,
            :trend_percentage, :confidence, :created_at
        )
        """,
        grain_rows,
    )

    risk_indicators = report.get("raw_risk_indicators", [])
    risk_overview = " || ".join(
        normalize_whitespace(
            " | ".join(
                part
                for part in [
                    clean_text(indicator.get("indicator")),
                    clean_text(indicator.get("observation")),
                    clean_text(indicator.get("context")),
                ]
                if part
            )
        )
        for indicator in risk_indicators
    ) or None
    system_metrics = report.get("system_level_risks") or report.get("system_level_metrics") or {}

    connection.execute(
        f"""
        INSERT INTO {SYSTEM_METRICS_TABLE} (
            id, source, time_period, time_period_start_year, time_period_end_year,
            baseline_comparison, baseline_start_year, baseline_end_year,
            import_requirement_ratio_wheat, export_surplus_ratio_rice,
            buffer_stock_index_wheat, raw_risk_indicator_count, risk_overview, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            source,
            time_period,
            period_start_year,
            period_end_year,
            baseline_comparison,
            baseline_start_year,
            baseline_end_year,
            system_metrics.get("import_requirement_ratio_wheat"),
            system_metrics.get("export_surplus_ratio_rice"),
            system_metrics.get("buffer_stock_index_wheat"),
            len(risk_indicators),
            risk_overview,
            created_at,
        ),
    )

    insight_rows = [
        {
            "source": source,
            "time_period": time_period,
            "insight_order": index,
            "insight": clean_text(insight),
            "created_at": created_at,
        }
        for index, insight in enumerate(report.get("key_insights", []), start=1)
    ]
    connection.executemany(
        f"""
        INSERT INTO {GRAIN_INSIGHTS_TABLE} (source, time_period, insight_order, insight, created_at)
        VALUES (:source, :time_period, :insight_order, :insight, :created_at)
        """,
        insight_rows,
    )

    return len(grain_rows), 1, len(insight_rows)


def load_disaster_report(path: Path) -> dict[str, Any]:
    raw_text = path.read_text(encoding="utf-8")
    sanitized_text = re.sub(r"(?<=\d)\s*\[cite:[^\]]+\]", "", raw_text)
    return json.loads(sanitized_text)


def commodity_bucket(food_supply_impact: dict[str, str], level: str) -> str | None:
    commodities = [commodity for commodity, severity in food_supply_impact.items() if clean_text(severity) == level]
    return ", ".join(commodities) if commodities else None


def ingest_disaster_report(connection: sqlite3.Connection, created_at: str) -> tuple[int, int]:
    report_path = resolve_data_file("Disaster_report_information.json")
    report = load_disaster_report(report_path)

    metadata = report.get("report_metadata", {})
    final_reporting_date = parse_date_to_iso(metadata.get("final_reporting_date"))
    report_status = clean_text(metadata.get("status"))
    report_sources = " | ".join(clean_text(source) for source in metadata.get("source_reports", []) if clean_text(source))
    confidence_score = report.get("confidence_score")

    signal_rows = []
    for signal in report.get("regional_operational_signals", []):
        affected_population = signal.get("affected_population", {})
        infrastructure_damage = signal.get("infrastructure_damage", {})
        derived_signals = signal.get("derived_signals", {})
        logistics = signal.get("logistics", {})
        food_supply_impact = signal.get("food_supply_impact", {})

        signal_rows.append(
            {
                "report_status": report_status,
                "report_final_date": final_reporting_date,
                "report_sources": report_sources or None,
                "confidence_score": confidence_score,
                "region": clean_text(signal.get("region")),
                "region_normalized": normalize_region(signal.get("region")),
                "signal_timestamp": parse_date_to_iso(signal.get("timestamp")),
                "severity_level": clean_text(signal.get("severity_level")),
                "severity_reason": clean_text(signal.get("severity_reason")),
                "deceased": affected_population.get("deceased"),
                "injured": affected_population.get("injured"),
                "persons_rescued": affected_population.get("persons_rescued"),
                "houses_partial": infrastructure_damage.get("houses_partial"),
                "houses_full": infrastructure_damage.get("houses_full"),
                "roads_km": infrastructure_damage.get("roads_km"),
                "bridges": infrastructure_damage.get("bridges"),
                "crop_loss_acres": signal.get("crop_loss_acres"),
                "supply_risk": clean_text(derived_signals.get("supply_risk")),
                "food_price_pressure": clean_text(derived_signals.get("food_price_pressure")),
                "logistics_disruption": clean_text(derived_signals.get("logistics_disruption")),
                "relief_camps": logistics.get("relief_camps"),
                "persons_in_camps": logistics.get("persons_in_camps"),
                "medical_camps": logistics.get("medical_camps"),
                "logistics_status": clean_text(logistics.get("status")),
                "high_impact_commodities": commodity_bucket(food_supply_impact, "High"),
                "medium_impact_commodities": commodity_bucket(food_supply_impact, "Medium"),
                "low_impact_commodities": commodity_bucket(food_supply_impact, "Low"),
                "created_at": created_at,
            }
        )

    connection.executemany(
        f"""
        INSERT INTO {DISASTER_SIGNALS_TABLE} (
            report_status, report_final_date, report_sources, confidence_score,
            region, region_normalized, signal_timestamp, severity_level,
            severity_reason, deceased, injured, persons_rescued, houses_partial,
            houses_full, roads_km, bridges, crop_loss_acres, supply_risk,
            food_price_pressure, logistics_disruption, relief_camps,
            persons_in_camps, medical_camps, logistics_status,
            high_impact_commodities, medium_impact_commodities,
            low_impact_commodities, created_at
        )
        VALUES (
            :report_status, :report_final_date, :report_sources, :confidence_score,
            :region, :region_normalized, :signal_timestamp, :severity_level,
            :severity_reason, :deceased, :injured, :persons_rescued, :houses_partial,
            :houses_full, :roads_km, :bridges, :crop_loss_acres, :supply_risk,
            :food_price_pressure, :logistics_disruption, :relief_camps,
            :persons_in_camps, :medical_camps, :logistics_status,
            :high_impact_commodities, :medium_impact_commodities,
            :low_impact_commodities, :created_at
        )
        """,
        signal_rows,
    )

    contradiction_rows = [
        {
            "report_final_date": final_reporting_date,
            "issue": clean_text(item.get("issue")),
            "description": clean_text(item.get("description")),
            "created_at": created_at,
        }
        for item in report.get("contradictions", [])
    ]
    connection.executemany(
        f"""
        INSERT INTO {CONTRADICTIONS_TABLE} (report_final_date, issue, description, created_at)
        VALUES (:report_final_date, :issue, :description, :created_at)
        """,
        contradiction_rows,
    )

    return len(signal_rows), len(contradiction_rows)


def fetch_table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLE_ORDER:
        count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        counts[table] = int(count)
    return counts


def main() -> None:
    created_at = utc_now_iso()
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.execute("PRAGMA journal_mode = WAL;")
        connection.execute("PRAGMA synchronous = NORMAL;")
        connection.execute("PRAGMA temp_store = MEMORY;")

        recreate_schema(connection)
        ingest_climate(connection, created_at)
        ingest_prices(connection, created_at)
        ingest_grain_report(connection, created_at)
        ingest_disaster_report(connection, created_at)

        counts = fetch_table_counts(connection)

    print(f"SQLite database populated at {DB_PATH}")
    for table in TABLE_ORDER:
        print(f"{table}: {counts[table]}")


if __name__ == "__main__":
    main()
