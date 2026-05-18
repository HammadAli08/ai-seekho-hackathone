import asyncio
import logging
import sys
import os

# Ensure we can import from the data module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.fetchers.pbs_fetcher import fetch_prices
from data.fetchers.rss_fetcher import fetch_news
from data.fetchers.wfp_fetcher import fetch_wfp_prices

logging.basicConfig(level=logging.INFO)

async def main():
    print("=== Testing PBS Fetcher ===")
    prices = await fetch_prices()
    print(f"PBS Prices fetched: {len(prices)} records.")
    if prices:
        print(f"Sample PBS record: {prices[0]}")
    
    print("\n=== Testing RSS News Fetcher ===")
    news = await fetch_news()
    print(f"News articles fetched: {len(news)}")
    if news:
        print(f"Sample News record: {news[0]['title']}")
        
    print("\n=== Testing WFP Fetcher ===")
    wfp = await fetch_wfp_prices()
    print(f"WFP Prices fetched: {len(wfp)} records.")
    if wfp:
        print(f"Sample WFP record: {wfp[0]}")

if __name__ == "__main__":
    asyncio.run(main())
