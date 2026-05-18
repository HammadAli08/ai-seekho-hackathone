from services.gemini_service import call_gemini
from utils.json_utils import parse_llm_json
import json, logging
from datetime import datetime

logger = logging.getLogger(__name__)


IMPACT_PROMPT = """
You are FaslBot's Impact Analyst Agent for Pakistan agricultural markets.
INSIGHT IDENTIFIED:
{insight}
RELEVANT PRICE DATA:
{price_data}
YOUR TASK:
Analyze the real-world impact of this insight on Pakistani farmers, traders, and consumers.
Be specific about:
  - Which stakeholder groups are affected (use realistic Pakistani population estimates)
  - How much money is at stake in PKR (estimate based on typical trade volumes)
  - What the consequence chain looks like if no action is taken
  - How many hours/days until the opportunity/risk window closes
Return ONLY valid JSON matching this schema:
{{
  "affected_stakeholders": [
    {{
      "group": "string",
      "population_estimate": "string",
      "impact_type": "revenue_loss|revenue_gain|cost_increase|opportunity",
      "impact_magnitude": "string",
      "urgency_for_this_group": "high|medium|low"
    }}
  ],
  "estimated_value_at_stake_pkr": 0,
  "estimated_value_readable": "string",
  "consequence_if_no_action": "string",
  "time_sensitivity": "string",
  "severity_score": 0.0
}}
"""


async def impact_analyst_agent(state: dict) -> dict:
    logger.info("[Agent 3] ImpactAnalystAgent starting...")
    trace_entry = {"agent": "ImpactAnalystAgent", "step": 3, "started_at": datetime.now().isoformat()}

    if not state.get("insight"):
        trace_entry["skipped"] = "No insight to analyze"
        return {"impact": None, "agent_trace": [trace_entry]}

    try:
        prompt = IMPACT_PROMPT.format(
            insight=json.dumps(state["insight"], indent=2),
            price_data=json.dumps(state.get("processed_prices", {}).get("summary", {}), indent=2)
        )

        response = await call_gemini(prompt, temperature=0.2)

        impact = parse_llm_json(response)
        if impact is None:
            raise ValueError("Failed to parse impact JSON from LLM response")

        trace_entry["output"] = impact
        trace_entry["reasoning"] = f"Severity: {impact.get('severity_score')}/10. Value at stake: {impact.get('estimated_value_readable')}"
        trace_entry["completed_at"] = datetime.now().isoformat()

        return {"impact": impact, "agent_trace": [trace_entry]}

    except Exception as e:
        logger.error(f"[Agent 3] ImpactAnalyst failed: {e}")
        trace_entry["error"] = str(e)
        return {"impact": None, "agent_trace": [trace_entry]}