import pytest
import uuid
from sutram_core.streams.redis_streams import StreamProducer, StreamConsumerGroup
from sutram_core.events.execution import ExecutionStartedEvent


@pytest.mark.asyncio
async def test_producer_publishes_message(fake_redis):
    producer = StreamProducer(redis=fake_redis)
    event = ExecutionStartedEvent(
        tenant_id=uuid.uuid4(),
        execution_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
    )
    message_id = await producer.publish("executions", event)
    assert message_id is not None

    # Verify it landed in the stream
    messages = await fake_redis.xrange("executions")
    assert len(messages) == 1


@pytest.mark.asyncio
async def test_consumer_group_reads_and_acks(fake_redis):
    producer = StreamProducer(redis=fake_redis)
    consumer = StreamConsumerGroup(redis=fake_redis)

    event = ExecutionStartedEvent(
        tenant_id=uuid.uuid4(),
        execution_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
    )
    await producer.publish("executions", event)

    # Create group before reading
    await fake_redis.xgroup_create("executions", "obs-workers", id="0", mkstream=True)

    messages = await consumer.read(
        stream="executions",
        group="obs-workers",
        consumer_name="worker-1",
        count=10,
    )
    assert len(messages) == 1
    msg_id, data = messages[0]
    assert data["event_type"] == "execution.started"

    # ACK
    await consumer.ack("executions", "obs-workers", msg_id)
    # Verify pending count is now 0
    pending = await fake_redis.xpending("executions", "obs-workers")
    assert pending["pending"] == 0


@pytest.mark.asyncio
async def test_producer_returns_string_message_id(fake_redis):
    producer = StreamProducer(redis=fake_redis)
    event = ExecutionStartedEvent(
        tenant_id=uuid.uuid4(),
        execution_id=uuid.uuid4(),
        workflow_id=uuid.uuid4(),
    )
    message_id = await producer.publish("executions", event)
    assert isinstance(message_id, str)
    # Redis Stream IDs are in format "timestamp-sequence"
    assert "-" in message_id


@pytest.mark.asyncio
async def test_consumer_returns_empty_list_when_no_messages(fake_redis):
    consumer = StreamConsumerGroup(redis=fake_redis)
    await fake_redis.xgroup_create("empty-stream", "group", id="0", mkstream=True)
    messages = await consumer.read(
        stream="empty-stream",
        group="group",
        consumer_name="worker-1",
        count=10,
        block_ms=None,  # non-blocking: omits BLOCK option, returns immediately
    )
    assert messages == []
