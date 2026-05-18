"""
Chat Agent Router — Pakistan Food Security Intelligence Engine

Exposes the Chat Agent's endpoints under /api/v1/chat/...
This module imports from chat_agent/ and does NOT touch any existing FaslBot code.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("chat_agent_router")

router = APIRouter(prefix="/api/v1/chat", tags=["Chat Agent"])


# ── Request Models ──────────────────────────────────────────────────────────

class RunAgentRequest(BaseModel):
    regions: list[str] | None = Field(
        default=None, description="Pakistan regions to assess."
    )
    refresh: bool = Field(
        default=True,
        description="Refresh Apify news and WeatherAPI data before reasoning.",
    )
    use_openai: bool = Field(
        default=True,
        description="Use OpenAI tool-calling agent when an API key is available.",
    )
    user_query: str | None = Field(
        default=None,
        description="Natural language query for time/geo intent extraction.",
    )


class SimulationRequest(BaseModel):
    action_chain: list[str] = Field(
        ..., min_length=1, description="Intervention steps to simulate."
    )
    region: str = Field(
        default="National",
        description="Region for the hypothetical simulation.",
    )


# ── Ensure DB schema on first import ────────────────────────────────────────

def _ensure_chat_db():
    """Initialize chat agent's SQLite schema (idempotent)."""
    try:
        from chat_agent.db import ensure_schema
        ensure_schema()
        logger.info("Chat agent SQLite schema verified.")
    except Exception as e:
        logger.warning(f"Chat agent DB init warning: {e}")


_ensure_chat_db()


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/run-agent")
def chat_run_agent(request: Request, payload: RunAgentRequest | None = None) -> dict[str, Any]:
    """
    Run the Intelligence Chat Agent.
    Performs geo/time resolution, multi-source data retrieval,
    causal reasoning, and risk signal computation.
    """
    from chat_agent.agent import run_agent
    from chat_agent.db import canonical_regions

    payload = payload or RunAgentRequest()
    started = time.perf_counter()
    logger.info(
        "Chat agent requested regions=%s refresh=%s use_openai=%s query=%s",
        payload.regions or canonical_regions(),
        payload.refresh,
        payload.use_openai,
        payload.user_query,
    )
    result = run_agent(
        regions=payload.regions,
        refresh=payload.refresh,
        use_openai=payload.use_openai,
        user_query=payload.user_query,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "Chat agent completed in %.0fms signals=%s actions=%s",
        elapsed_ms,
        len(result.get("signals", [])),
        len(result.get("action_chain", [])),
    )
    return result


@router.get("/signals")
def chat_signals(
    request: Request,
    region: str | None = Query(default=None),
) -> dict[str, Any]:
    """Fetch computed risk signals for one or all regions."""
    from chat_agent.tools import compute_risk_signals
    from chat_agent.db import canonical_regions

    regions = [region] if region else canonical_regions()
    logger.info("Chat signals requested regions=%s", regions)
    result = compute_risk_signals(regions)
    logger.info("Chat signals completed count=%s", len(result))
    return {"signals": result}


@router.post("/simulate")
def chat_simulate(
    request: Request,
    params: SimulationRequest,
) -> dict[str, Any]:
    """Run a hypothetical intervention simulation."""
    from chat_agent.simulation import run_simulation

    logger.info(
        "Chat simulation requested region=%s steps=%s",
        params.region,
        len(params.action_chain),
    )
    result = run_simulation(params.action_chain, region=params.region)
    logger.info(
        "Chat simulation completed region=%s before_aff=%.2f after_aff=%.2f",
        params.region,
        float(result["before"].get("affordability_index", 0.0)),
        float(result["after"].get("affordability_index", 0.0)),
    )
    return {
        "simulation": {"before": result["before"], "after": result["after"]},
        "step_impacts": result["step_impacts"],
    }


@router.get("/logs")
def chat_logs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    """Fetch reasoning trace and action logs from the Chat Agent."""
    from chat_agent.db import fetch_action_logs

    logger.info("Chat logs requested limit=%s", limit)
    records = fetch_action_logs(limit=limit)
    reasoning_trace = [
        record["trace_message"]
        for record in records
        if record.get("trace_message")
    ]
    logger.info("Chat logs completed count=%s", len(records))
    return {"logs": records, "reasoning_trace": reasoning_trace}
