from typing import List, Dict
import statistics

TRANSPORT_COST_PER_KG = 10  # PKR average inter-city transport
ARBITRAGE_THRESHOLD = 0.15   # 15% price gap minimum
SPIKE_THRESHOLD = 1.40       # 40% above median = spike


def compare_prices(price_records: List[Dict]) -> Dict:
    by_commodity = {}
    for record in price_records:
        commodity = record.get("commodity", "Unknown")
        city = record.get("city", "Unknown")
        price = record.get("price_pkr", 0)

        if commodity not in by_commodity:
            by_commodity[commodity] = {}
        if city not in by_commodity[commodity]:
            by_commodity[commodity][city] = price
        else:
            by_commodity[commodity][city] = (by_commodity[commodity][city] + price) / 2

    arbitrage = _detect_arbitrage(by_commodity)
    spikes = _detect_spikes(by_commodity)

    return {
        "by_commodity": by_commodity,
        "arbitrage_opportunities": arbitrage,
        "price_spikes": spikes,
        "summary": {
            "total_records": len(price_records),
            "commodities": len(by_commodity),
            "cities": len(set(r["city"] for r in price_records)),
            "max_spread": max(arbitrage, key=lambda x: x["spread_pct"]) if arbitrage else None,
            "biggest_spike": max(spikes, key=lambda x: x["spike_pct"]) if spikes else None
        }
    }


def _detect_arbitrage(by_commodity: Dict) -> List[Dict]:
    opportunities = []
    for commodity, city_prices in by_commodity.items():
        if len(city_prices) < 2:
            continue

        prices = list(city_prices.items())
        min_city, min_price = min(prices, key=lambda x: x[1])
        max_city, max_price = max(prices, key=lambda x: x[1])

        spread_pct = (max_price - min_price) / min_price
        net_spread = max_price - min_price - TRANSPORT_COST_PER_KG

        if spread_pct >= ARBITRAGE_THRESHOLD:
            opportunities.append({
                "commodity": commodity,
                "buy_city": min_city,
                "sell_city": max_city,
                "buy_price": round(min_price, 2),
                "sell_price": round(max_price, 2),
                "spread_pct": round(spread_pct * 100, 1),
                "spread_pkr": round(max_price - min_price, 2),
                "net_spread_pkr": round(net_spread, 2),
                "viability": "high" if net_spread / min_price > 0.10 else "medium"
            })

    return sorted(opportunities, key=lambda x: x["spread_pct"], reverse=True)


def _detect_spikes(by_commodity: Dict) -> List[Dict]:
    spikes = []
    for commodity, city_prices in by_commodity.items():
        if len(city_prices) < 2:
            continue

        all_prices = list(city_prices.values())
        median_price = statistics.median(all_prices)

        for city, price in city_prices.items():
            if price > median_price * SPIKE_THRESHOLD:
                spikes.append({
                    "commodity": commodity,
                    "city": city,
                    "current_price": round(price, 2),
                    "median_price": round(median_price, 2),
                    "spike_pct": round((price - median_price) / median_price * 100, 1)
                })

    return sorted(spikes, key=lambda x: x["spike_pct"], reverse=True)