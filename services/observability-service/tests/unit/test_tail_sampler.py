import pytest
import uuid
from app.sampling.tail_sampler import TailSampler


@pytest.mark.asyncio
async def test_buffer_span_stores_in_redis(fake_redis):
    sampler = TailSampler(redis=fake_redis, ttl_seconds=600, sample_rate=0.10, slow_threshold_ms=30_000)
    execution_id = uuid.uuid4()
    await sampler.buffer_span(
        execution_id=execution_id,
        span_key="step:0",
        span_data={"event_type": "execution.step.completed", "step_index": "0", "duration_ms": "500"},
    )
    key = f"trace:buffer:{execution_id}"
    stored = await fake_redis.hget(key, "step:0")
    assert stored is not None


@pytest.mark.asyncio
async def test_should_keep_trace_with_failure(fake_redis):
    sampler = TailSampler(redis=fake_redis, ttl_seconds=600, sample_rate=0.10, slow_threshold_ms=30_000)
    execution_id = uuid.uuid4()
    await sampler.mark_has_failure(execution_id)
    assert await sampler.should_keep(execution_id, total_duration_ms=100) is True


@pytest.mark.asyncio
async def test_should_keep_slow_trace(fake_redis):
    sampler = TailSampler(redis=fake_redis, ttl_seconds=600, sample_rate=0.10, slow_threshold_ms=30_000)
    execution_id = uuid.uuid4()
    assert await sampler.should_keep(execution_id, total_duration_ms=35_000) is True


@pytest.mark.asyncio
async def test_flush_returns_buffered_spans(fake_redis):
    sampler = TailSampler(redis=fake_redis, ttl_seconds=600, sample_rate=0.10, slow_threshold_ms=30_000)
    execution_id = uuid.uuid4()
    await sampler.buffer_span(execution_id, "step:0", {"event_type": "execution.step.completed"})
    await sampler.buffer_span(execution_id, "step:1", {"event_type": "execution.step.completed"})
    spans = await sampler.flush(execution_id)
    assert len(spans) == 2


@pytest.mark.asyncio
async def test_flush_clears_buffer(fake_redis):
    sampler = TailSampler(redis=fake_redis, ttl_seconds=600, sample_rate=0.10, slow_threshold_ms=30_000)
    execution_id = uuid.uuid4()
    await sampler.buffer_span(execution_id, "step:0", {"event_type": "execution.started"})
    await sampler.flush(execution_id)
    key = f"trace:buffer:{execution_id}"
    exists = await fake_redis.exists(key)
    assert exists == 0


@pytest.mark.asyncio
async def test_duplicate_span_key_overwrites_not_duplicates(fake_redis):
    """Redis Hash prevents duplicate spans on PEL redelivery."""
    sampler = TailSampler(redis=fake_redis, ttl_seconds=600, sample_rate=0.10, slow_threshold_ms=30_000)
    execution_id = uuid.uuid4()
    await sampler.buffer_span(execution_id, "step:0", {"duration_ms": "500"})
    await sampler.buffer_span(execution_id, "step:0", {"duration_ms": "500"})  # same key
    spans = await sampler.flush(execution_id)
    assert len(spans) == 1  # not 2
