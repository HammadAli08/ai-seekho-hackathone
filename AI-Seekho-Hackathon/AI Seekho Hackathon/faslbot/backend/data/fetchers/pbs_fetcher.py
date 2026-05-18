import httpx
import pandas as pd
import json
import random
import re
import io
from datetime import date, datetime
from pathlib import Path
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

PBS_PRICE_URL = "https://www.pbs.gov.pk/price-statistics"
SEED_DATA_PATH = Path(__file__).parent.parent / "seeds" / "sample_prices.json"

_price_cache: List[Dict] = []
_cache_timestamp: datetime = None
CACHE_TTL_SECONDS = 3600


async def fetch_prices(force_refresh: bool = False) -> List[Dict]:
    global _price_cache, _cache_timestamp

    if not force_refresh and _price_cache and _cache_timestamp:
        age = (datetime.now() - _cache_timestamp).seconds
        if age < CACHE_TTL_SECONDS:
            logger.info(f"Returning cached PBS prices (age: {age}s)")
            return _price_cache

    # Clear cache on force refresh
    if force_refresh:
        _price_cache = []
        _cache_timestamp = None

    try:
        prices = await _fetch_live_prices()
        _price_cache = prices
        _cache_timestamp = datetime.now()
        logger.info(f"Fetched {len(prices)} live price records from PBS")
        return prices
    except Exception as e:
        logger.warning(f"PBS live fetch failed: {e}. Using fallback seed data.")
        return _load_fallback_prices()


async def _fetch_live_prices() -> List[Dict]:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(PBS_PRICE_URL, headers={"User-Agent": "FaslBot/1.0 (Hackathon)"})
        response.raise_for_status()

        # Find the annexureExcel link using regex
        match = re.search(r'annexureExcel\s*:\s*["\']([^"\']+\.xlsx)["\']', response.text, re.IGNORECASE)
        if not match:
            # Fallback to reportExcel if annexure not found
            match = re.search(r'reportExcel\s*:\s*["\']([^"\']+\.xlsx)["\']', response.text, re.IGNORECASE)

        if not match:
            raise ValueError("No Excel link found on PBS page")

        excel_path = match.group(1)
        # Ensure it's an absolute URL
        if not excel_path.startswith("http"):
            excel_path = f"https://www.pbs.gov.pk/{excel_path.lstrip('/')}"

        logger.info(f"Downloading PBS Excel from: {excel_path}")
        excel_resp = await client.get(excel_path)
        excel_resp.raise_for_status()

        excel_file = pd.ExcelFile(io.BytesIO(excel_resp.content))
        return _parse_pbs_excel(excel_file)


def _parse_pbs_excel(excel_file: pd.ExcelFile) -> List[Dict]:
    records = []
    today = date.today().isoformat()

    # Only match raw commodities, not processed products
    commodity_map = {
        "wheat": "گندم",
        "rice basmati": "چاول بسمتی",
        "tomato": "ٹماٹر",
        "onion": "پیاز",
        "potato": "آلو",
        "sugar": "چینی",
        "beef": "بیف",
        "mutton": "مٹن",
        "chicken": "مرغی"
    }

    # Commodities to EXCLUDE (processed products) - less aggressive
    exclude_patterns = ["flour", "bag", "bread", "ghee", "oil", "powder", "paste", "cooked"]

    def parse_unit_to_kg(unit_str: str) -> float:
        """Convert PBS unit string to kg multiplier."""
        if pd.isna(unit_str):
            return 1.0
        unit_str = str(unit_str).lower().strip()
        match = re.search(r'([\d.]+)\s*(kg|gm|g)', unit_str)
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            if unit.startswith('g'):
                return value / 1000.0
            else:
                return value
        return 1.0

    # Target cities
    target_cities = {
        "islamabad": "islamabad",
        "karachi": "karachi",
        "lahore": "lahore",
        "peshawar": "peshawar",
        "multan": "multan",
    }

    for sheet_name in excel_file.sheet_names:
        try:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
            if len(df) < 10:
                continue

            # Find ALL header rows (PBS sometimes has multiple sections)
            header_indices = []
            for i in range(min(40, len(df))):
                row = [str(x).lower() if pd.notna(x) else '' for x in df.iloc[i].tolist()]
                if any('description' in s for s in row) or any('unit' in s for s in row):
                    header_indices.append(i)
                    logger.info(f"Found header at row {i}")

            if not header_indices:
                continue

            # Process each header section
            for header_idx in header_indices:
                header_row = df.iloc[header_idx].tolist()
                logger.info(f"Sheet {sheet_name}: Header at row {header_idx}")

                # Check if this header has MIN/AVG/MAX pattern (Appendix-A style)
                # or if previous row has city names
                has_min_max = False
                city_name_row = header_row  # Default to header row for city names
                if header_idx + 1 < len(df):
                    next_row = df.iloc[header_idx + 1].tolist()
                    next_row_str = [str(x).upper() if pd.notna(x) else '' for x in next_row]
                    has_min_max = any('AVG' in s for s in next_row_str)

                # If next row has MIN/MAX, the PREVIOUS row likely has city names
                if has_min_max and header_idx > 0:
                    city_name_row = df.iloc[header_idx - 1].tolist()
                    logger.info(f"Using previous row {header_idx - 1} for city names")

                # Find city columns - PBS format varies
                city_cols = {}
                for idx in range(3, min(len(city_name_row), 20)):
                    cell = city_name_row[idx]
                    if pd.isna(cell):
                        continue
                    cell_str = str(cell).lower().replace('-', '').replace(' ', '')

                    # Check for city names (normalize hyphens and spaces)
                    for t_city, t_key in target_cities.items():
                        normalized_city = t_city.replace('-', '').replace(' ', '')
                        if normalized_city in cell_str or t_key in cell_str:
                            # If next row has MIN/AVG/MAX, we need to find AVG column
                            target_col = idx
                            if has_min_max and header_idx + 1 < len(df):
                                next_row = df.iloc[header_idx + 1].tolist()
                                # Look for AVG in next row at this position or after
                                for offset in range(3):  # Check next 3 columns
                                    if idx + offset < len(next_row):
                                        next_cell = str(next_row[idx + offset]).upper() if pd.notna(next_row[idx + offset]) else ''
                                        if 'AVG' in next_cell:
                                            target_col = idx + offset
                                            break

                            # Verify this column has numeric data (check 2 rows after header)
                            if header_idx + 2 < len(df):
                                sample = df.iloc[header_idx + 2, target_col]
                                try:
                                    float(sample) if pd.notna(sample) else None
                                    city_cols[t_key] = target_col
                                    logger.info(f"Found {t_key} at column {target_col} ({cell})")
                                    break
                                except:
                                    pass

                if not city_cols:
                    logger.info(f"No target cities in section {header_idx}, skipping")
                    continue

                # Find data start row (skip header and any blank rows)
                data_start = header_idx + 1
                while data_start < len(df):
                    first_cell = df.iloc[data_start, 0] if len(df.columns) > 0 else None
                    if pd.notna(first_cell):
                        try:
                            int(first_cell)  # Row numbers typically start at 1
                            break
                        except:
                            pass
                    data_start += 1

                logger.info(f"Processing data from row {data_start}")

                # Parse data rows
                for i in range(data_start, len(df)):
                    desc = df.iloc[i, 1] if len(df.columns) > 1 else None
                    if pd.isna(desc):
                        continue

                    desc_str = str(desc).strip()
                    desc_lower = desc_str.lower()

                    # Skip excluded items
                    if any(p in desc_lower for p in exclude_patterns):
                        continue

                    # Match commodities (handle plurals like "Tomatoes" -> "tomato")
                    mapped_commodity = None
                    mapped_urdu = None
                    for key, urdu in commodity_map.items():
                        # Check both full match and partial match
                        if key in desc_lower or desc_lower.startswith(key):
                            mapped_commodity = desc_str
                            mapped_urdu = urdu
                            break

                    if not mapped_commodity:
                        continue

                    # Get unit (column 3 in Appendix-B, column 2 in Appendix-A)
                    # Only treat as a unit if it contains letters like kg, gm, ltr, bag
                    unit_val = None
                    if len(df.columns) > 3:
                        unit_val = df.iloc[i, 3]
                    if pd.isna(unit_val) and len(df.columns) > 2:
                        unit_val = df.iloc[i, 2]

                    # Stricter unit detection: only treat as unit if contains letters
                    unit_str = ""
                    if pd.notna(unit_val):
                        unit_str = str(unit_val).strip()
                        # Only accept as unit if it contains letters (kg, gm, ltr, bag, etc.)
                        has_letters = any(c.isalpha() for c in unit_str)
                        if not has_letters:
                            # This is likely a numeric price, not a unit - reset
                            unit_str = ""
                            unit_val = None

                    # Normalize to 1-unit basis
                    if unit_str:
                        # Extract the numeric part and unit from strings like "20kg", "1 kg"
                        match = re.search(r'([\d.]+)\s*(kg|gm|g|ltr|bag|liter|litre)', unit_str, re.IGNORECASE)
                        if match:
                            numeric_part = float(match.group(1))
                            unit_part = match.group(2).lower()
                            # Convert to kg multiplier
                            if unit_part.startswith('g') and not unit_part.startswith('gm'):
                                unit_kg = numeric_part / 1000.0
                            elif unit_part == 'kg':
                                unit_kg = numeric_part
                            elif unit_part in ('ltr', 'liter', 'litre'):
                                unit_kg = numeric_part  # Assume 1L ≈ 1kg for simplicity
                            elif unit_part == 'bag':
                                # Bags vary, but commonly 20kg or 50kg - default to 20
                                unit_kg = numeric_part if numeric_part > 1 else 20.0
                            else:
                                unit_kg = 1.0
                            # Normalize unit to base (kg, gm, etc.)
                            if unit_part.startswith('g') and len(unit_part) == 2:
                                base_unit = 'gm'
                            elif unit_part == 'bag':
                                base_unit = 'kg'  # Normalize bag to kg
                            else:
                                base_unit = 'kg'
                        else:
                            unit_kg = 1.0
                            base_unit = 'kg'
                    else:
                        # No unit found, default to kg
                        unit_kg = 1.0
                        base_unit = 'kg'

                    # Extract prices for each city
                    for city, col_idx in city_cols.items():
                        if col_idx >= len(df.columns):
                            continue

                        price_val = df.iloc[i, col_idx]
                        try:
                            raw_price = float(price_val)
                            if raw_price > 0:
                                # Normalize to 1-unit basis
                                price_per_unit = raw_price / unit_kg if unit_kg > 0 else raw_price

                                records.append({
                                    "commodity": mapped_commodity,
                                    "commodity_urdu": mapped_urdu,
                                    "city": city.title(),
                                    "price_pkr": round(price_per_unit, 2),
                                    "unit": base_unit,
                                    "date": today,
                                    "source": "PBS Live",
                                    "raw_price": raw_price,
                                    "raw_unit": unit_str or "kg",
                                    "is_fallback": False
                                })
                                logger.info(f"  {city}: {mapped_commodity} = {price_per_unit} PKR/{base_unit} (raw: {raw_price} {unit_str or 'kg'})")
                        except (ValueError, TypeError):
                            continue

        except Exception as e:
            logger.warning(f"Failed to parse sheet {sheet_name}: {e}")

    return records


def _load_fallback_prices() -> List[Dict]:
    with open(SEED_DATA_PATH, 'r', encoding='utf-8') as f:
        seed = json.load(f)

    today = date.today().isoformat()
    for record in seed:
        record["price_pkr"] = round(record["price_pkr"] * random.uniform(0.97, 1.03), 2)
        record["date"] = today
        record["is_fallback"] = True

    logger.info(f"Loaded {len(seed)} fallback price records")
    return seed