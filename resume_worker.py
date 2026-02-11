import asyncio
from app.core.config import settings
from app.services.resume_processing_service import run_once as run_once_service


async def worker_loop():
    while True:
        await run_once_service(processed_by="worker")
        await asyncio.sleep(settings.resume_process_interval_seconds)


if __name__ == "__main__":
    asyncio.run(worker_loop())
