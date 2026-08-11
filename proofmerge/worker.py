import asyncio

from proofmerge.config import get_settings
from proofmerge.database import create_schema, dispose_engine
from proofmerge.events import KafkaReviewQueue
from proofmerge.orchestrator import ReviewOrchestrator


async def run_worker() -> None:
    settings = get_settings()
    if settings.queue_backend != "kafka":
        raise RuntimeError("Worker requires PROOFMERGE_QUEUE_BACKEND=kafka")
    await create_schema()
    queue = KafkaReviewQueue(settings)
    orchestrator = ReviewOrchestrator(settings)
    try:
        async for review_id in queue.consume():
            await orchestrator.run(review_id)
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(run_worker())
