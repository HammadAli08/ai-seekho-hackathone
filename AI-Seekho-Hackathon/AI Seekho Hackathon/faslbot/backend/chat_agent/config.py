"""
Shared configuration for Pakistan Food Security Intelligence Engine.

All constants that appear in more than one module are defined here
to eliminate drift between ingestion, scoring, and agent logic.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Food-security keyword lists
# ---------------------------------------------------------------------------
# Single source of truth for keyword categories used by:
#   - scraper.FOOD_KEYWORDS
#   - news_ingest.ALLOWED_KEYWORDS
#   - agent._collect_signal_inputs  (inline list)
# ---------------------------------------------------------------------------

FOOD_SECURITY_KEYWORDS: list[str] = [
    # Staples & commodities
    "wheat",
    "flour",
    "atta",
    "rice",
    "sugar",
    "edible oil",
    "maize",
    "cotton",
    # Market & price signals
    "food price",
    "food prices",
    "price hike",
    "inflation",
    "shortage",
    "supply chain",
    # Trade
    "import",
    "export",
    # Hazards & agencies
    "flood",
    "drought",
    "ndma",
    "pdma",
    # Sector
    "crop",
    "harvest",
    "mandi",
    "agriculture",
]

# News-ingest filter: keywords that gate whether a scraped article is stored.
NEWS_FILTER_KEYWORDS: list[str] = [
    "wheat",
    "rice",
    "flour",
    "inflation",
    "flood",
    "drought",
    "ndma",
    "pdma",
    "food prices",
    "supply chain",
    "shortage",
    "import",
    "export",
]

# Agent / signal-inputs additional context keywords added alongside the
# primary commodity when querying news.
SIGNAL_INPUT_CONTEXT_KEYWORDS: list[str] = [
    "wheat",
    "flour",
    "food",
    "flood",
    "inflation",
    "shortage",
    "import",
    "rice",
    "drought",
    "ndma",
]

# ---------------------------------------------------------------------------
# Scoring thresholds
# ---------------------------------------------------------------------------
PRICE_SPIKE_WARNING_PCT: float = 12.0       # % above baseline → spike signal
PRICE_SPIKE_EMERGENCY_PCT: float = 30.0     # % above baseline → emergency action
SIGNAL_MIN_RELEVANCE: float = 0.30          # rank_and_select_signals gate
SIGNAL_MIN_RECENCY: float = 0.05            # rank_and_select_signals gate
SIGNAL_MIN_FINAL_SCORE: float = 25.0        # rank_and_select_signals gate

# ---------------------------------------------------------------------------
# Signal scoring weights  (relevance × W1  +  recency × W2  +  credibility × W3)
# ---------------------------------------------------------------------------
WEIGHT_RELEVANCE: float = 0.35
WEIGHT_RECENCY: float = 0.45
WEIGHT_CREDIBILITY: float = 0.20

# ---------------------------------------------------------------------------
# Time-intent freshness windows (days)
# ---------------------------------------------------------------------------
REAL_TIME_MAX_AGE_DAYS: int = 7
RECENT_MAX_AGE_DAYS: int = 30
HISTORICAL_MAX_AGE_DAYS: int = 365 * 2  # 2 years

# ---------------------------------------------------------------------------
# Simulation delta caps (index points 0-100 scale)
# ---------------------------------------------------------------------------
SIM_STOCK_DELTA_PRICE: float = -8.0
SIM_STOCK_DELTA_SUPPLY: float = 6.0
SIM_STOCK_DELTA_AFFORDABILITY: float = 5.0
SIM_DISTRIBUTE_DELTA_PRICE: float = -4.0
SIM_DISTRIBUTE_DELTA_SUPPLY: float = 9.0
SIM_DISTRIBUTE_DELTA_AFFORDABILITY: float = 7.0
SIM_DISTRIBUTE_DELTA_LOGISTICS: float = -10.0
SIM_IMPORT_DELTA_PRICE: float = -10.0
SIM_IMPORT_DELTA_SUPPLY: float = 8.0
SIM_LOGISTICS_DELTA_LOGISTICS: float = -12.0
SIM_LOGISTICS_DELTA_SUPPLY: float = 7.0
SIM_SUBSIDY_DELTA_AFFORDABILITY: float = 12.0
SIM_MONITOR_DELTA_PRICE: float = -6.0
