from services.firebase_service import update_pipeline_status
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def audit_logger_agent(state: dict) -> dict:
    logger.info("[Agent 6] AuditLoggerAgent starting...")
    trace_entry = {"agent": "AuditLoggerAgent", "step": 6, "started_at": datetime.now().isoformat()}

    try:
        await update_pipeline_status(state["run_id"], "completed", state)
        trace_entry["output"] = "Pipeline saved to Firestore"
        trace_entry["completed_at"] = datetime.now().isoformat()
        state["status"] = "completed"
        return {"agent_trace": [trace_entry], "status": "completed"}

    except Exception as e:
        logger.error(f"[Agent 6] AuditLogger failed: {e}")
        trace_entry["error"] = str(e)
        return {"agent_trace": [trace_entry], "status": "error"}