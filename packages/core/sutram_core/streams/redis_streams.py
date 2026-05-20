from __future__ import annotations
import redis.asyncio as aioredis
from ..events.base import BaseEvent


class StreamProducer:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def publish(self, stream: str, event: BaseEvent) -> str:
        """Publish event to Redis Stream. Returns message ID as string."""
        data = event.to_stream_dict()
        message_id = await self._redis.xadd(stream, data)
        return message_id.decode() if isinstance(message_id, bytes) else message_id


class StreamConsumerGroup:
    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis

    async def read(
        self,
        stream: str,
        group: str,
        consumer_name: str,
        count: int = 10,
        block_ms: int | None = 1000,
    ) -> list[tuple[str, dict[str, str]]]:
        """Read pending messages for this consumer.

        Returns list of (message_id, data) tuples. Data values are all strings.

        block_ms: milliseconds to block waiting for messages.
                  None = non-blocking (returns immediately if no messages).
                  1000 = block up to 1 second (default).

        Precondition: consumer group must exist (create via xgroup_create before calling).
        """
        results = await self._redis.xreadgroup(
            groupname=group,
            consumername=consumer_name,
            streams={stream: ">"},
            count=count,
            block=block_ms,
        )
        if not results:
            return []
        messages = []
        for _stream, entries in results:
            for message_id, fields in entries:
                msg_id = message_id.decode() if isinstance(message_id, bytes) else message_id
                decoded = {
                    (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
                    for k, v in fields.items()
                }
                messages.append((msg_id, decoded))
        return messages

    async def ack(self, stream: str, group: str, message_id: str) -> None:
        """Acknowledge a message, removing it from the pending entries list."""
        await self._redis.xack(stream, group, message_id)
