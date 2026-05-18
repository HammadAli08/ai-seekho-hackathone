from services.gemini_service import call_gemini
from utils.json_utils import parse_llm_json
import json, logging
from datetime import datetime

logger = logging.getLogger(__name__)


ACTION_PROMPT = """
You are FaslBot's Action Planner Agent.
INSIGHT:
{insight}
IMPACT:
{impact}
YOUR TASK:
Generate exactly 3 concrete, ranked action recommendations executable in Pakistan.
Available action types:
- TELENOR_SMS_BLAST
- MANDI_PRICE_UPDATE
- PROCUREMENT_ADVISORY
Rank actions by: urgency × impact × feasibility
Return ONLY a valid JSON array of exactly 3 action objects matching this schema:
[{{
  "rank": 1,
  "action_type": "string",
  "title": "string (max 10 words)",
  "title_urdu": "string",
  "description": "string",
  "target": {{"city": "string", "commodity": "string", "audience": "string", "count": 0}},
  "expected_impact": "string",
  "execution_simulation": {{"api_endpoint": "string", "payload_preview": {{}}, "estimated_reach": "string", "estimated_time": "string"}},
  "urgency": "high|medium|low",
  "effort": "low|medium|high"
}}]
"""


async def action_planner_agent(state: dict) -> dict:
    logger.info("[Agent 4] ActionPlannerAgent starting...")
    trace_entry = {"agent": "ActionPlannerAgent", "step": 4, "started_at": datetime.now().isoformat()}

    if not state.get("insight") or not state.get("impact"):
        trace_entry["skipped"] = "Missing insight or impact data"
        return {"actions": [], "agent_trace": [trace_entry]}

    try:
        prompt = ACTION_PROMPT.format(insight=json.dumps(state["insight"]), impact=json.dumps(state["impact"]))
        response = await call_gemini(prompt, temperature=0.4)

        actions = parse_llm_json(response)
        if actions is None:
            raise ValueError("Failed to parse actions JSON from LLM response")
        if not isinstance(actions, list):
            actions = [actions]

        top_action_title = actions[0].get('title') if actions else "none"
        trace_entry["output"] = actions
        trace_entry["reasoning"] = f"Generated {len(actions)} actions. Top action: {top_action_title}"
        trace_entry["completed_at"] = datetime.now().isoformat()

        return {"actions": actions, "agent_trace": [trace_entry]}

    except Exception as e:
        logger.error(f"[Agent 4] ActionPlanner failed: {e}")
        trace_entry["error"] = str(e)
        return {"actions": [], "agent_trace": [trace_entry]}