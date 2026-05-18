from services.sms_service import send_sms_blast
from datetime import datetime
import logging, asyncio

logger = logging.getLogger(__name__)


async def action_executor_agent(state: dict) -> dict:
    logger.info("[Agent 5] ActionExecutorAgent starting...")
    trace_entry = {"agent": "ActionExecutorAgent", "step": 5, "started_at": datetime.now().isoformat()}

    if not state.get("actions"):
        trace_entry["skipped"] = "No actions to execute"
        return {"executed_action": None, "execution_result": None, "agent_trace": [trace_entry]}

    top_action = state["actions"][0]
    sim_log = []

    def log_step(msg: str):
        sim_log.append(f"{datetime.now().strftime('%H:%M:%S')} - {msg}")
        logger.info(f"[Agent 5] {msg}")

    try:
        log_step(f"Starting {top_action['action_type']}")
        before_state = {"alerts_active": 0, "farmers_notified": 0}

        result_data = {}
        if top_action["action_type"] == "TELENOR_SMS_BLAST":
            log_step("Connecting to Telenor SMS gateway (simulated)...")
            message = f"FaslBot Alert: {state['insight'].get('headline_urdu', '')}"
            result_data = await send_sms_blast(message, top_action["target"].get("count", 100), top_action["target"].get("city", "Lahore"))

        after_state = {"alerts_active": 1, "farmers_notified": top_action["target"].get("count", 0)}
        log_step("✅ Execution complete")

        execution_result = {
            "action_executed": top_action,
            "execution_status": "success",
            "before_state": before_state,
            "after_state": after_state,
            "simulation_log": sim_log,
            "sample_output": result_data.get("sample_message", "Action Executed")
        }

        trace_entry["output"] = execution_result
        trace_entry["completed_at"] = datetime.now().isoformat()

        return {"executed_action": top_action, "execution_result": execution_result, "agent_trace": [trace_entry]}

    except Exception as e:
        logger.error(f"[Agent 5] ActionExecutor failed: {e}")
        trace_entry["error"] = str(e)
        return {"executed_action": top_action, "execution_result": {"status": "failed"}, "agent_trace": [trace_entry]}