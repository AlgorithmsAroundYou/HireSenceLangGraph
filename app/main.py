from fastapi import FastAPI
from app.models.db import engine
import asyncio
import logging

from app.services.resume_processing_service import run_once
from app.core.config import settings
from app.api import auth_routes, chat_routes, jd_routes, resume_routes


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


app = FastAPI(title="HireSence AI Agent")


async def _resume_worker_background():
    """Background task: periodically process pending resumes while app runs."""

    while True:
        try:
            processed = await run_once(processed_by="api-worker")
            logger.info("Resume worker tick: processed %d resumes", processed)
        except Exception as exc:
            logger.exception("Resume worker encountered an error: %s", exc)
        await asyncio.sleep(settings.resume_process_interval_seconds)


@app.on_event("startup")
async def on_startup():
    logger.info("Application startup: running sql/init.sql")
    raw_conn = engine.raw_connection()
    try:
        with open("sql/init.sql", "r") as f:
            sql_script = f.read()
        cursor = raw_conn.cursor()
        cursor.executescript(sql_script)
        raw_conn.commit()
        logger.info("Database initialization from init.sql completed")
    except Exception as exc:
        logger.exception("Error during database initialization: %s", exc)
    finally:
        raw_conn.close()

    # Start background resume processing worker
    asyncio.create_task(_resume_worker_background())
    logger.info("Background resume worker started")


app.include_router(auth_routes.router, prefix="/api")
app.include_router(chat_routes.router, prefix="/api")
app.include_router(jd_routes.router, prefix="/api")
app.include_router(resume_routes.router, prefix="/api")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
