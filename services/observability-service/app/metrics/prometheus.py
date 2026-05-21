"""Prometheus metric definitions and recording helpers.

Metrics are module-level singletons — safe to import from anywhere.
The /metrics HTTP endpoint is served by prometheus_client.make_asgi_app()
mounted at app startup in main.py, separate from the /v1/ business routes.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ── Execution metrics ──────────────────────────────────────────────────

EXECUTION_TOTAL = Counter(
    "sutram_execution_total",
    "Total workflow executions by tenant and status",
    ["tenant_id", "status"],
)

EXECUTION_DURATION = Histogram(
    "sutram_execution_duration_seconds",
    "Workflow execution duration in seconds",
    ["tenant_id", "status"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)

EXECUTION_COST = Histogram(
    "sutram_execution_cost_usd",
    "Workflow execution cost in USD",
    ["tenant_id"],
    buckets=[0.01, 0.05, 0.10, 0.25, 0.50, 1.00, 5.00, 10.00],
)

STEP_DURATION = Histogram(
    "sutram_step_duration_seconds",
    "Individual step execution duration in seconds",
    ["workflow_id", "step_name"],
    buckets=[0.1, 0.5, 1, 5, 10, 30, 60],
)

MEMORY_LATENCY = Histogram(
    "sutram_memory_retrieval_latency_seconds",
    "Memory retrieval latency in seconds",
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0],
)

ACTIVE_EXECUTIONS = Gauge(
    "sutram_active_executions",
    "Number of currently running executions",
    ["tenant_id"],
)

CHECKPOINT_FAILURES = Counter(
    "sutram_checkpoint_failures_total",
    "Total checkpoint write failures",
)


# ── Recording helpers ──────────────────────────────────────────────────

def record_execution_started(tenant_id: str) -> None:
    """Increment active execution gauge when an execution begins."""
    ACTIVE_EXECUTIONS.labels(tenant_id=tenant_id).inc()


def record_execution_completed(
    tenant_id: str,
    status: str,
    duration_ms: int,
    cost_usd: float,
) -> None:
    EXECUTION_TOTAL.labels(tenant_id=tenant_id, status=status).inc()
    EXECUTION_DURATION.labels(tenant_id=tenant_id, status=status).observe(duration_ms / 1000)
    EXECUTION_COST.labels(tenant_id=tenant_id).observe(cost_usd)
    if status in ("COMPLETED", "FAILED", "CANCELLED"):
        ACTIVE_EXECUTIONS.labels(tenant_id=tenant_id).dec()


def record_step_completed(
    workflow_id: str,
    step_name: str,
    duration_ms: int,
) -> None:
    STEP_DURATION.labels(workflow_id=workflow_id, step_name=step_name).observe(duration_ms / 1000)


def record_memory_searched(latency_ms: int) -> None:
    MEMORY_LATENCY.observe(latency_ms / 1000)
