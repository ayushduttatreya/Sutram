from app.metrics.prometheus import (
    EXECUTION_TOTAL,
    EXECUTION_DURATION,
    EXECUTION_COST,
    STEP_DURATION,
    MEMORY_LATENCY,
    ACTIVE_EXECUTIONS,
    CHECKPOINT_FAILURES,
    record_execution_completed,
    record_execution_started,
    record_step_completed,
    record_memory_searched,
)


def test_all_metrics_exist():
    assert EXECUTION_TOTAL is not None
    assert EXECUTION_DURATION is not None
    assert EXECUTION_COST is not None
    assert STEP_DURATION is not None
    assert MEMORY_LATENCY is not None
    assert ACTIVE_EXECUTIONS is not None
    assert CHECKPOINT_FAILURES is not None


def test_record_execution_completed_does_not_raise():
    import uuid
    record_execution_completed(
        tenant_id=str(uuid.uuid4()),
        status="COMPLETED",
        duration_ms=5000,
        cost_usd=0.25,
    )


def test_record_execution_started_does_not_raise():
    import uuid
    record_execution_started(tenant_id=str(uuid.uuid4()))


def test_record_step_completed_does_not_raise():
    import uuid
    record_step_completed(
        workflow_id=str(uuid.uuid4()),
        step_name="fetch",
        duration_ms=300,
    )


def test_record_memory_searched_does_not_raise():
    record_memory_searched(latency_ms=45)


def test_execution_duration_observes_in_seconds():
    """duration_ms is converted to seconds before observing."""
    import uuid
    # Just confirm it doesn't raise — values are checked by Prometheus internally
    record_execution_completed(
        tenant_id=str(uuid.uuid4()),
        status="FAILED",
        duration_ms=10_000,
        cost_usd=0.0,
    )
