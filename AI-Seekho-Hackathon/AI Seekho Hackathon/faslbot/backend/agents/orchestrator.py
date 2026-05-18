from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Optional, Annotated
import operator
from uuid import uuid4
from datetime import datetime
import logging

from .data_ingestor import data_ingestor_agent
from .insight_extractor import insight_extractor_agent
from .impact_analyst import impact_analyst_agent
from .action_planner import action_planner_agent
from .action_executor import action_executor_agent
from .audit_logger import audit_logger_agent
from services.firebase_service import update_pipeline_status

logger = logging.getLogger(__name__)


class PipelineState(TypedDict):
    run_id: str
    started_at: str
    raw_prices: List[Dict]
    raw_news: List[Dict]
    processed_prices: Dict
    insight: Optional[Dict]
    impact: Optional[Dict]
    actions: List[Dict]
    executed_action: Optional[Dict]
    execution_result: Optional[Dict]
    agent_trace: Annotated[List[Dict], operator.add]
    status: str
    error: Optional[str]


def build_pipeline() -> StateGraph:
    graph = StateGraph(PipelineState)

    graph.add_node("data_ingestor", data_ingestor_agent)
    graph.add_node("insight_extractor", insight_extractor_agent)
    graph.add_node("impact_analyst", impact_analyst_agent)
    graph.add_node("action_planner", action_planner_agent)
    graph.add_node("action_executor", action_executor_agent)
    graph.add_node("audit_logger", audit_logger_agent)

    graph.set_entry_point("data_ingestor")
    graph.add_edge("data_ingestor", "insight_extractor")
    graph.add_edge("insight_extractor", "impact_analyst")
    graph.add_edge("impact_analyst", "action_planner")
    graph.add_edge("action_planner", "action_executor")
    graph.add_edge("action_executor", "audit_logger")
    graph.add_edge("audit_logger", END)

    return graph.compile()


pipeline = build_pipeline()


async def run_pipeline() -> Dict:
    run_id = str(uuid4())[:8]
    initial_state = PipelineState(
        run_id=run_id, started_at=datetime.now().isoformat(), raw_prices=[], raw_news=[],
        processed_prices={}, insight=None, impact=None, actions=[], executed_action=None,
        execution_result=None, agent_trace=[], status="running", error=None
    )

    logger.info(f"=== FaslBot Pipeline Starting | Run ID: {run_id} ===")
    await update_pipeline_status(run_id, "running", {})

    try:
        final_state = await pipeline.ainvoke(initial_state)
        logger.info(f"=== Pipeline Completed | Run ID: {run_id} ===")
        return dict(final_state)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        await update_pipeline_status(run_id, "error", {"error": str(e)})
        raise