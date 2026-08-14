import asyncio

from PR_Agent.config import get_settings
from PR_Agent.database import create_schema, dispose_engine
from PR_Agent.events import KafkaReviewQueue
from PR_Agent.orchestrator import ReviewOrchestrator


async def run_worker() -> None:
    settings = get_settings()
    if settings.queue_backend != "kafka":
        raise RuntimeError("Worker requires PR_AGENT_QUEUE_BACKEND=kafka")
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
