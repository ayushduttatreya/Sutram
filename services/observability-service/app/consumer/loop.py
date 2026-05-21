# services/observability-service/app/consumer/loop.py
from __future__ import annotations

import asyncio
import logging

import redis.asyncio as aioredis
from sutram_core.streams.redis_streams import StreamConsumerGroup

from app.consumer.dispatcher import UnknownEventType, parse_event
from app.dependencies import get_db_session_context, get_redis_buffer
from app.metrics.prometheus import CHECKPOINT_FAILURES
from app.sampling.tail_sampler import TailSampler
from app.settings import get_settings

logger = logging.getLogger(__name__)

_RECLAIM_EVERY = 50


async def ensure_consumer_groups(redis: aioredis.Redis) -> None:
    settings = get_settings()
    for stream in (settings.executions_stream, settings.memory_stream):
        try:
            await redis.xgroup_create(stream, settings.consumer_group, id="$", mkstream=True)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise


async def run_consumer_loop(redis_streams: aioredis.Redis) -> None:
    settings = get_settings()
    consumer = StreamConsumerGroup(redis=redis_streams)
    redis_buffer = get_redis_buffer()
    sampler = TailSampler(
        redis=redis_buffer,
        ttl_seconds=settings.trace_buffer_ttl_seconds,
        sample_rate=settings.fast_execution_sample_rate,
        slow_threshold_ms=settings.slow_execution_threshold_ms,
    )

    await ensure_consumer_groups(redis_streams)
    messages_processed = 0

    while True:
        try:
            for stream_name in (settings.executions_stream, settings.memory_stream):
                messages = await consumer.read(
                    stream=stream_name,
                    group=settings.consumer_group,
                    consumer_name=settings.consumer_name,
                    count=settings.consumer_poll_count,
                    block_ms=settings.consumer_block_ms,
                )
                for msg_id, data in messages:
                    await _process_one(redis_streams, stream_name, msg_id, data, consumer, sampler)
                    messages_processed += 1

            if messages_processed > 0 and messages_processed % _RECLAIM_EVERY == 0:
                for stream_name in (settings.executions_stream, settings.memory_stream):
                    await _reclaim_pending(redis_streams, stream_name, consumer, sampler)

        except asyncio.CancelledError:
            logger.info("Consumer loop cancelled — shutting down")
            break
        except Exception as e:
            logger.error("Consumer loop error (will retry): %s", e, exc_info=True)
            await asyncio.sleep(1)


async def _process_one(
    redis_streams: aioredis.Redis,
    stream_name: str,
    msg_id: str,
    data: dict[str, str],
    consumer: StreamConsumerGroup,
    sampler: TailSampler,
) -> None:
    settings = get_settings()
    try:
        event = parse_event(data)
    except UnknownEventType:
        await consumer.ack(stream_name, settings.consumer_group, msg_id)
        return

    try:
        async with get_db_session_context() as session:
            from app.consumer.handler import EventHandler

            handler = EventHandler(sampler=sampler, session=session)
            await handler.handle(event, data)
        await consumer.ack(stream_name, settings.consumer_group, msg_id)
    except Exception as e:
        logger.error("Failed to process %s: %s", msg_id, e, exc_info=True)
        CHECKPOINT_FAILURES.inc()


async def _reclaim_pending(
    redis_streams: aioredis.Redis,
    stream_name: str,
    consumer: StreamConsumerGroup,
    sampler: TailSampler,
) -> None:
    settings = get_settings()
    try:
        result = await redis_streams.xautoclaim(
            name=stream_name,
            groupname=settings.consumer_group,
            consumername=settings.consumer_name,
            min_idle_time=settings.reclaim_min_idle_ms,
            start_id="0-0",
            count=50,
        )
        messages = result[1] if isinstance(result, (list, tuple)) and len(result) > 1 else []
        for entry in messages:
            msg_id, fields = entry
            decoded = {
                k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
                for k, v in fields.items()
            }
            await _process_one(
                redis_streams,
                stream_name,
                msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
                decoded,
                consumer,
                sampler,
            )
    except Exception as e:
        logger.warning("PEL reclaim failed for %s: %s", stream_name, e)
