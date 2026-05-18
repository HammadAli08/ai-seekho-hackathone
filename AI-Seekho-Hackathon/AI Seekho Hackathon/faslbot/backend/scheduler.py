from apscheduler.schedulers.asyncio import AsyncIOScheduler
from agents.orchestrator import run_pipeline
from config import settings
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def scheduled_pipeline_run():
    logger.info("Starting scheduled FaslBot pipeline run...")
    try:
        await run_pipeline()
    except Exception as e:
        logger.error(f"Scheduled run failed: {e}")


def start_scheduler():
    if settings.PIPELINE_AUTO_RUN:
        scheduler.add_job(scheduled_pipeline_run, 'interval', seconds=settings.PRICE_REFRESH_INTERVAL)
        scheduler.start()
        logger.info(f"Scheduler started. Running every {settings.PRICE_REFRESH_INTERVAL}s")
    else:
        logger.info("Scheduler disabled via PIPELINE_AUTO_RUN config.")