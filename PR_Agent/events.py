import json
from collections.abc import AsyncIterator

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from PR_Agent.config import Settings


class KafkaReviewQueue:
    def __init__(self, settings: Settings) -> None:
        self.bootstrap_servers = settings.kafka_bootstrap_servers
        self.topic = settings.kafka_topic

    async def publish(self, review_id: str) -> None:
        producer = AIOKafkaProducer(bootstrap_servers=self.bootstrap_servers)
        await producer.start()
        try:
            await producer.send_and_wait(
                self.topic,
                json.dumps({"review_id": review_id}).encode(),
            )
        finally:
            await producer.stop()

    async def consume(self) -> AsyncIterator[str]:
        consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id="PR_Agent-workers",
            enable_auto_commit=False,
        )
        await consumer.start()
        try:
            async for message in consumer:
                payload = json.loads(message.value.decode())
                yield str(payload["review_id"])
                await consumer.commit()
        finally:
            await consumer.stop()
