import httpx
from typing import List, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

WFP_API_URL = "https://api.vam.wfp.org/markets/prices"
WFP_COUNTRY_CODE = "PK"

_wfp_cache: List[Dict] = []
_wfp_cache_time: datetime = None
WFP_CACHE_TTL = 86400  # 24 hours


async def fetch_wfp_prices() -> List[Dict]:
    global _wfp_cache, _wfp_cache_time

    if _wfp_cache and _wfp_cache_time:
        age = (datetime.now() - _wfp_cache_time).seconds
        if age < WFP_CACHE_TTL:
            return _wfp_cache

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                WFP_API_URL,
                params={"CountryCode": WFP_COUNTRY_CODE, "page": 1, "pageSize": 100},
                headers={"Accept": "application/json"}
            )
            resp.raise_for_status()
            data = resp.json()

        records = _normalize_wfp_data(data)
        _wfp_cache = records
        _wfp_cache_time = datetime.now()
        logger.info(f"WFP: fetched {len(records)} price records")
        return records
    except Exception as e:
        logger.warning(f"WFP fetch failed: {e}")
        return []


def _normalize_wfp_data(data: dict) -> List[Dict]:
    records = []
    commodity_map = {
        "Wheat flour": "Wheat", "Rice": "Rice IRRI",
        "Tomatoes": "Tomato", "Onions": "Onion",
        "Potatoes": "Potato", "Sugar": "Sugar"
    }

    def parse_wfp_unit(unit_str):
        """Normalize WFP unit to 1-unit basis (kg)."""
        if not unit_str:
            return 1.0, "kg"
        unit_str = str(unit_str).lower().strip()
        # Check for patterns like "50 kg", "1 kg", "25kg"
        import re
        match = re.search(r'([\d.]+)\s*(kg|gm|g|ltr|liter|litre|bag)', unit_str)
        if match:
            numeric = float(match.group(1))
            unit = match.group(2)
            if unit.startswith('g') and len(unit) == 1:
                # grams to kg
                return numeric / 1000.0, "kg"
            elif unit == 'kg':
                return numeric, "kg"
            elif unit in ('ltr', 'liter', 'litre'):
                return numeric, "ltr"
            elif unit == 'bag':
                # Normalize bags to kg (assume typical bag weight)
                return numeric, "kg"
        return 1.0, "kg"

    items = data.get("items", data.get("data", []))
    for item in items:
        commodity_raw = item.get("commodity", {}).get("name", "")
        commodity = commodity_map.get(commodity_raw, commodity_raw)
        price = item.get("price", None)
        city = item.get("market", {}).get("name", "Pakistan")
        unit_raw = item.get("unit", {}).get("name", "kg")

        if price and commodity:
            # Normalize to 1-unit basis
            multiplier, base_unit = parse_wfp_unit(unit_raw)
            price_per_unit = float(price) / multiplier if multiplier > 0 else float(price)

            records.append({
                "commodity": commodity,
                "commodity_urdu": "",
                "city": city,
                "price_pkr": round(price_per_unit, 2),
                "unit": base_unit,
                "date": item.get("date", datetime.now().date().isoformat()),
                "source": "WFP",
                "is_fallback": False,
                "raw_price": float(price),
                "raw_unit": unit_raw
            })
    return records