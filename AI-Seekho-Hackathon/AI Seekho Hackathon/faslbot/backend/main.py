from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config import settings
from agents.orchestrator import run_pipeline
from scheduler import start_scheduler
from services.firebase_service import get_latest_insights, get_latest_actions, get_latest_prices
from routers.chat_router import router as chat_router
import logging

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FaslBot Backend Starting Up...")
    start_scheduler()
    yield
    logger.info("FaslBot Backend Shutting Down...")


app = FastAPI(title="FaslBot Backend API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Chat Agent Integration ───────────────────────────────────────────────────
app.include_router(chat_router)


@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "service": "faslbot_backend",
        "mode": settings.SMS_MODE,
        "gemini_model": settings.GEMINI_MODEL
    }


@app.post("/api/v1/trigger-pipeline")
async def trigger_pipeline_endpoint(background_tasks: BackgroundTasks):
    try:
        # We start the LangGraph pipeline in the background so the HTTP request doesn't block
        background_tasks.add_task(run_pipeline)
        return {"status": "accepted", "message": "FaslBot pipeline started in background"}
    except Exception as e:
        logger.error(f"Failed to trigger pipeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pipeline trigger failed: {str(e)}")


@app.get("/api/v1/insights")
async def latest_insights(limit: int = 3):
    try:
        if limit < 1 or limit > 20:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 20")
        insights = await get_latest_insights(limit=limit)
        return {"status": "success", "data": insights}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get insights: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve insights: {str(e)}")


@app.get("/api/v1/actions")
async def latest_actions(limit: int = 20):
    """Get the latest executed actions with SMS messages."""
    try:
        if limit < 1 or limit > 50:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 50")
        actions = await get_latest_actions(limit=limit)
        return {"status": "success", "data": actions}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get actions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve actions: {str(e)}")


@app.get("/api/v1/prices")
async def latest_prices():
    """Get the latest parsed prices organized by city and commodity."""
    try:
        prices_data = await get_latest_prices()
        return {"status": "success", "data": prices_data}
    except Exception as e:
        logger.error(f"Failed to get prices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve prices: {str(e)}")