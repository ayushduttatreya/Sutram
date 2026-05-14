# Sutram

**Durable execution and persistent memory infrastructure for production AI workflows.**

Sutram is designed for teams that want AI systems to behave less like fragile scripts and more like dependable software. It gives long-running AI workflows the ability to pause, recover, remember context, expose traceable decisions, and operate safely across tenants.

In plain English: Sutram helps AI applications survive failures, keep useful memory, and show exactly what happened during execution.

For engineers and recruiters: Sutram is a production-oriented architecture for durable workflow orchestration, semantic memory retrieval, execution tracing, multi-tenant isolation, and cloud-native operations.

---

## Table of Contents

1. [Why Sutram Exists](#why-sutram-exists)
2. [Product Vision](#product-vision)
3. [Core Capabilities](#core-capabilities)
4. [Architecture at a Glance](#architecture-at-a-glance)
5. [System Context](#system-context)
6. [Architecture Principles](#architecture-principles)
7. [Logical Architecture](#logical-architecture)
8. [Component Architecture](#component-architecture)
9. [Data Architecture](#data-architecture)
10. [Security Architecture](#security-architecture)
11. [Reliability and Recovery](#reliability-and-recovery)
12. [Infrastructure and Deployment](#infrastructure-and-deployment)
13. [Observability](#observability)
14. [Quality Targets](#quality-targets)
15. [Technical Decisions](#technical-decisions)
16. [API Surface](#api-surface)
17. [Operational Runbooks](#operational-runbooks)
18. [Roadmap](#roadmap)
19. [Glossary](#glossary)

---

## Why Sutram Exists

Modern AI applications are powerful, but production AI workflows often fail in three predictable ways:

| Problem | What Happens | Why It Matters |
| --- | --- | --- |
| Execution fragility | A workflow crashes halfway through and starts from zero | Wasted tokens, wasted compute, broken user trust |
| Context amnesia | The system forgets prior decisions, user preferences, and outcomes | AI feels inconsistent and expensive to operate |
| Observability gap | Nobody can explain why an AI workflow made a decision | Debugging, compliance, and trust become difficult |

Sutram addresses these problems with three platform primitives:

1. **Durable execution**: workflows checkpoint state and resume after failures.
2. **Persistent memory**: AI systems retrieve useful context across sessions.
3. **Execution observability**: every important action is traceable and auditable.

The result is an AI workflow platform built around reliability, continuity, and trust.

---

## Product Vision

Sutram is the execution backbone for production AI systems.

```text
Client Apps / SDKs / Agents
        |
        v
Sutram Platform
  - Durable Workflow Engine
  - Persistent Memory Service
  - Observability and Audit Layer
        |
        v
Databases, Queues, Object Storage, LLM Providers, Customer APIs
```

The platform is intentionally practical. It uses proven infrastructure patterns, avoids unnecessary distributed-system complexity in the MVP, and focuses innovation on the product layer: reliable AI execution.

---

## Core Capabilities

### Durable Workflow Execution

Sutram executes AI workflows as resumable state machines. Each execution tracks the current step, variables, cost, heartbeat, checkpoints, and trace context.

Key behaviors:

- Create checkpoints before expensive or risky operations.
- Resume from the latest valid checkpoint after crashes.
- Pause safely on recoverable errors.
- Preserve execution state for debugging and replay.
- Enforce cost, time, and tenant-level resource limits.

### Persistent Memory

Sutram stores memory as structured, searchable, tenant-scoped knowledge.

Supported memory types:

| Type | Meaning | Example |
| --- | --- | --- |
| Episodic | What happened | "This workflow failed on step 4 yesterday." |
| Semantic | What is known | "This customer prefers concise executive summaries." |
| Procedural | How to do something | "For invoice extraction, validate totals before export." |

Retrieval combines hot cache lookup, vector similarity search, metadata filters, recency, and access frequency.

### Execution Observability

Every workflow execution produces structured traces, metrics, logs, and audit records.

Sutram tracks:

- Workflow duration
- Step-level latency
- LLM call count
- Token and cost usage
- Checkpoints created
- Errors and retries
- Security-sensitive events
- Tenant-level usage patterns

---

## Architecture at a Glance

```text
+--------------------------------------------------------------+
|                      Client Applications                      |
|          Python SDK | REST API | Web Console | Agents         |
+-----------------------------+--------------------------------+
                              |
                              v
+--------------------------------------------------------------+
|                       API Gateway Layer                       |
|      Auth | Rate Limits | Request Validation | Tenant Scope   |
+-----------------------------+--------------------------------+
                              |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
+----------------+   +----------------+   +--------------------+
| Workflow       |   | Memory         |   | Observability      |
| Service        |   | Service        |   | Service            |
|                |   |                |   |                    |
| State Machine  |   | Vector Search  |   | Traces             |
| Checkpoints    |   | Hybrid Search  |   | Metrics            |
| Recovery       |   | Compression    |   | Audit Logs         |
+--------+-------+   +--------+-------+   +---------+----------+
         |                    |                     |
         +--------------------+---------------------+
                              |
                              v
+--------------------------------------------------------------+
|                      Persistence Layer                        |
|       PostgreSQL + pgvector | Redis | TimescaleDB | S3        |
+--------------------------------------------------------------+
```

---

## System Context

Sutram sits between developers building AI workflows and the external systems those workflows depend on.

```text
Data Scientists / Engineers / Product Teams
        |
        | Define workflows, execute jobs, inspect traces
        v
+------------------------------------------------+
|                 Sutram Platform                |
|  Durable Execution | Memory | Observability    |
+-------------+----------------+-----------------+
              |                |
              v                v
       LLM Providers      Customer APIs
       OpenAI, etc.       CRMs, data tools,
                           internal services
```

External dependencies are treated as unreliable by default. Sutram uses timeouts, retries, circuit breakers, idempotency, and checkpointing to reduce the blast radius of dependency failures.

---

## Architecture Principles

| Principle | Meaning |
| --- | --- |
| Durability first | Critical state is persisted before success is acknowledged |
| Fail safe by default | Workflows pause on uncertain errors instead of proceeding incorrectly |
| Observable by design | Traces, logs, metrics, and audit records are first-class outputs |
| Tenant isolation | Every request, query, trace, and memory item is scoped by tenant |
| API-first | Platform behavior is exposed through versioned APIs and SDKs |
| Boring technology first | Use proven infrastructure; innovate at the product layer |
| Stateless services | Application services can scale horizontally and recover cleanly |
| Evolutionary design | The MVP can grow toward larger deployments without a rewrite |

---

## Logical Architecture

Sutram follows a layered architecture.

```text
Presentation Layer
  REST API, Python SDK, Web Console

Application Layer
  Workflow orchestration, memory management, policy enforcement

Domain Layer
  Workflow state machine, execution context, memory model, tenant model

Infrastructure Layer
  Databases, queues, object storage, external clients, telemetry exporters
```

### Domain Model

```text
Tenant
  Workflow
    WorkflowDefinition
    WorkflowExecution
      ExecutionStep
      Checkpoint
      StepTrace
      ExecutionContext

  Memory
    MemoryItem
      EpisodicMemory
      SemanticMemory
      ProceduralMemory
    MemoryIndex

  Agent
    AgentIdentity
    AgentCredentials
    AgentPermissions
```

This model keeps product concepts understandable while giving engineers clear ownership boundaries.

---

## Component Architecture

### API Gateway

The API Gateway is the public entry point.

Responsibilities:

- Authenticate users and API keys.
- Resolve tenant context.
- Validate requests.
- Enforce rate limits.
- Route requests to internal services.
- Attach trace and correlation IDs.

Target quality:

- P95 gateway overhead below 50 ms
- Configurable tenant-level rate limits
- Strict request validation before service routing

### Workflow Service

The Workflow Service owns workflow definitions, execution lifecycle, checkpoints, and recovery.

Responsibilities:

- Create and version workflow definitions.
- Start asynchronous workflow executions.
- Track execution state.
- Create checkpoints.
- Resume paused or interrupted executions.
- Enforce cost and duration limits.

Execution states:

```text
PENDING -> RUNNING -> COMPLETED
             |
             +-> PAUSED -> RUNNING
             |
             +-> FAILED
```

Checkpoint strategy:

- Always checkpoint before expensive LLM calls.
- Checkpoint before high-risk external API calls.
- Checkpoint long-running steps.
- Keep checkpoint overhead below 5 percent of execution time.

### Memory Service

The Memory Service owns persistent context.

Responsibilities:

- Store memory items.
- Generate and store embeddings.
- Retrieve relevant memory using hybrid search.
- Compress older memories into summaries.
- Archive cold memory to object storage.

Storage tiers:

| Tier | Technology | Purpose |
| --- | --- | --- |
| Hot | Redis | Recently accessed memory and cached searches |
| Warm | PostgreSQL + pgvector | Durable memory and semantic retrieval |
| Cold | S3 | Long-term archive and compliance retention |

### Observability Service

The Observability Service turns AI execution into inspectable software behavior.

Responsibilities:

- Collect OpenTelemetry spans.
- Store execution traces.
- Aggregate metrics.
- Record audit logs.
- Power dashboards and incident response.

### Execution Engine

The Execution Engine is the heart of Sutram. It runs workflow steps using a durable state machine and checkpoint-aware recovery.

Core loop:

1. Load workflow definition.
2. Load latest checkpoint, if present.
3. Reconstruct execution context.
4. Execute each step.
5. Persist state and checkpoint when required.
6. Emit traces and metrics.
7. Complete, pause, or fail safely.

---

## Data Architecture

Sutram uses polyglot persistence because workflow state, semantic memory, cache data, traces, and archives have different access patterns.

| Data | Store | Reason |
| --- | --- | --- |
| Tenants | PostgreSQL | Strong consistency and relational constraints |
| Workflows | PostgreSQL | Versioned definitions and metadata |
| Executions | PostgreSQL | Durable state and transactional updates |
| Checkpoints | PostgreSQL | ACID recovery guarantees |
| Memory embeddings | PostgreSQL + pgvector | Semantic search without a separate vector DB |
| Hot cache | Redis | Low-latency lookup and coordination |
| Traces | TimescaleDB | Time-series query performance |
| Archives | S3 | Low-cost long-term retention |

### Core Tables

Important entities include:

- `tenants`
- `workflows`
- `workflow_executions`
- `checkpoints`
- `memory_items`
- `execution_traces`

### Consistency Guarantees

| Operation | Consistency | Why |
| --- | --- | --- |
| Checkpoint creation | Strong | Lost checkpoints mean lost recovery state |
| Execution status update | Strong | Users need accurate workflow state |
| Memory writes | Eventual where acceptable | Retrieval can tolerate slight lag |
| Trace writes | Eventual | Telemetry can be buffered and batched |

### Partitioning Strategy

The MVP begins with shared PostgreSQL tables scoped by `tenant_id`. At scale, Sutram can move to:

- Hash partitioning by tenant.
- Read replicas for query-heavy workloads.
- Dedicated shards for large tenants.
- Time-based archival for completed executions and traces.

---

## Security Architecture

Security is designed in layers.

| Layer | Controls |
| --- | --- |
| Network | VPC isolation, private subnets, WAF, DDoS protection |
| Identity | OAuth 2.0, OIDC, JWT, API keys |
| Authorization | RBAC and tenant-scoped permissions |
| Data protection | TLS in transit, AES-256 at rest, KMS-managed keys |
| Tenant isolation | Row-level security and tenant-aware service logic |
| Secrets | AWS Secrets Manager or equivalent managed secret store |
| Audit | Immutable logs for state changes and sensitive actions |

### Tenant Isolation

Every request is resolved to a tenant before accessing data. Services pass tenant context through the entire call path, and database queries are scoped by `tenant_id`.

For PostgreSQL deployments, row-level security can enforce this boundary:

```sql
ALTER TABLE workflow_executions ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_policy
ON workflow_executions
USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
```

---

## Reliability and Recovery

Sutram is built around the assumption that failures will happen.

Failure scenarios handled:

- Service process crash
- Worker crash during execution
- LLM provider timeout
- Customer API failure
- Database failover
- Redis interruption
- Network latency spike
- Partial workflow failure

Recovery flow:

1. Detect stuck execution through heartbeat monitoring.
2. Load the latest checkpoint.
3. Rebuild execution context.
4. Resume from the next safe step.
5. Preserve trace continuity.
6. Mark unrecoverable executions as paused or failed with diagnostic context.

Target recovery behavior:

| Scenario | Target |
| --- | --- |
| Service pod crash | Recover in under 1 minute |
| Stuck execution detection | Within 5 minutes |
| Checkpoint resume | Under 10 seconds |
| Database primary failover | Under 5 minutes |
| Availability | 99.9 percent |
| Durability | 99.99 percent |

---

## Infrastructure and Deployment

The MVP deployment targets a single AWS region with managed services.

```text
AWS Region
  Application Load Balancer
    ECS Fargate Services
      API Gateway
      Workflow Service
      Memory Service
      Observability Service
      Worker Pool

  Data Layer
    RDS PostgreSQL Multi-AZ
    ElastiCache Redis
    TimescaleDB
    S3
```

### Scaling Strategy

Application services are stateless and scale horizontally.

Workflow Service scaling triggers:

- Queue depth above threshold
- CPU above 70 percent
- Memory above 80 percent
- P95 execution start latency above target

Memory Service scaling triggers:

- Retrieval latency above 200 ms P95
- CPU above 60 percent
- Cache miss rate above threshold

Database scaling phases:

1. Single RDS primary for MVP.
2. Read replicas for read-heavy workloads.
3. Tenant-based partitioning.
4. Dedicated shards for large enterprise tenants.

### Deployment Pipeline

```text
Developer Commit
  -> GitHub Actions
  -> Unit Tests
  -> Integration Tests
  -> Lint and Type Checks
  -> Security Scan
  -> Build Docker Images
  -> Push to Registry
  -> Deploy to Staging
  -> End-to-End Tests
  -> Manual Production Approval
  -> Blue-Green or Canary Deployment
```

---

## Observability

Sutram treats observability as a product feature, not only an operations concern.

### Metrics

Key metrics:

- `workflow_execution_total`
- `workflow_execution_duration_seconds`
- `workflow_execution_cost_usd`
- `memory_retrieval_latency_seconds`
- `memory_items_total`
- `checkpoint_creation_duration_seconds`
- `checkpoint_failure_total`
- `db_query_duration_seconds`
- `system_health_score`

### Alerts

Critical alerts:

- Error rate above 5 percent for 5 minutes.
- Database unavailable for 1 minute.
- Checkpoint failure rate above 1 percent.
- Worker queue depth above capacity threshold.

Warning alerts:

- P95 API latency above 1 second.
- Memory retrieval latency above target.
- Connection pool saturation above 80 percent.
- Paused workflows growing faster than resolution rate.

---

## Quality Targets

| Attribute | Target |
| --- | --- |
| API response time | P95 below 500 ms |
| Memory retrieval | P95 below 200 ms |
| Workflow start latency | P95 below 2 seconds |
| Checkpoint creation | P95 below 100 ms |
| Regional throughput | 1,000 requests per second |
| Concurrent executions | 10,000 per region |
| Tenants | 1,000 MVP target |
| Trace coverage | 100 percent of executions |
| Execution success rate | Above 99 percent |

---

## Technical Decisions

### PostgreSQL as Primary Storage

PostgreSQL is selected for workflow state, checkpoints, tenants, and memory metadata.

Why:

- ACID transactions for checkpoint durability.
- Strong relational integrity.
- JSONB support for flexible workflow state.
- pgvector support for semantic memory retrieval.
- Mature operational tooling.

### pgvector Before a Dedicated Vector Database

For the MVP, pgvector keeps semantic retrieval close to the core data model.

Why:

- Fewer moving parts.
- Easier tenant isolation.
- Lower operational cost.
- Good enough performance for MVP scale.

Dedicated vector infrastructure can be introduced later if retrieval volume or ranking complexity demands it.

### Redis for Coordination and Hot Paths

Redis is used for:

- Hot cache.
- Pub/sub events.
- Celery backend.
- Distributed locks.
- Short-lived coordination state.

### Asynchronous Workflow Execution

Workflow execution is asynchronous by design.

Client flow:

1. Submit workflow.
2. Receive `execution_id`.
3. Poll status or receive webhook events.
4. Retrieve trace, result, and memory artifacts.

This avoids long HTTP connections and supports workflows that may run for minutes or hours.

### Fail-Safe Workflow Behavior

Recoverable errors move workflows into `PAUSED` instead of blindly retrying or failing immediately. This preserves context and enables human review.

---

## API Surface

### Workflow Management

```http
POST   /v1/workflows
GET    /v1/workflows
GET    /v1/workflows/{workflow_id}
PUT    /v1/workflows/{workflow_id}
DELETE /v1/workflows/{workflow_id}

POST   /v1/workflows/{workflow_id}/execute
GET    /v1/workflows/{workflow_id}/executions
GET    /v1/executions/{execution_id}
POST   /v1/executions/{execution_id}/pause
POST   /v1/executions/{execution_id}/resume
POST   /v1/executions/{execution_id}/cancel
```

### Memory Operations

```http
POST   /v1/memory/items
GET    /v1/memory/items/{item_id}
PUT    /v1/memory/items/{item_id}
DELETE /v1/memory/items/{item_id}

POST   /v1/memory/search
GET    /v1/memory/items?type={type}
```

### Observability

```http
GET /v1/traces/{execution_id}
GET /v1/metrics?start={timestamp}&end={timestamp}&metric={name}
GET /v1/audit-logs?start={timestamp}&end={timestamp}
```

---

## Operational Runbooks

### Start the Platform Locally

```bash
docker-compose -f docker-compose.data.yml up -d
alembic upgrade head
docker-compose -f docker-compose.services.yml up -d
./scripts/health-check.sh
```

### High Error Rate

Investigation:

1. Check service health dashboard.
2. Identify failing service from logs.
3. Inspect recent deployments.
4. Check external dependency status.
5. Confirm database and Redis health.

Resolution paths:

- Roll back recent deployment if regression is confirmed.
- Enable circuit breaker for failing external dependency.
- Scale workers if queue pressure is the root cause.
- Pause affected workflows if correctness is at risk.

### Database Failover

Expected behavior:

- RDS promotes standby.
- Services reconnect through managed endpoint.
- Workers retry transient database errors.
- Checkpoint recovery resumes interrupted executions.

Post-incident checks:

- Validate checkpoint integrity.
- Confirm no executions are stuck in `RUNNING`.
- Review trace gaps.
- File incident report with timeline and root cause.

---

## Roadmap

### MVP

- Durable workflow execution
- Checkpoint and resume
- Persistent semantic memory
- Multi-tenant data isolation
- REST API
- Python SDK
- Execution traces and metrics

### Post-MVP

- Web console for workflow monitoring
- Webhooks for execution lifecycle events
- Advanced memory ranking
- Human review queues
- Enterprise SSO
- Policy engine for workflow governance
- Multi-region disaster recovery

### Future Exploration

- Multi-agent coordination
- Cross-organization workflow federation
- Marketplace for reusable agent skills
- Advanced cost optimization
- Dedicated vector infrastructure at scale

---

## Recruiter and Engineering Signal

Sutram demonstrates experience with:

- Distributed systems design
- Durable execution and recovery semantics
- Multi-tenant SaaS architecture
- Vector search and AI memory systems
- Cloud-native deployment on AWS
- Security and tenant isolation
- Observability with traces, metrics, and audit logs
- API-first product engineering
- Reliability engineering and incident response

This project is not just an AI wrapper. It is the infrastructure layer AI products need when they move from demos to production.

---

## Glossary

| Term | Definition |
| --- | --- |
| Checkpoint | A durable snapshot of workflow state used for recovery |
| Durable execution | Execution that can survive failures and resume safely |
| Episodic memory | Memory about specific events or past executions |
| Semantic memory | Memory about facts, concepts, and meanings |
| Procedural memory | Memory about how to perform tasks |
| Execution context | Runtime state passed between workflow steps |
| Tenant | A customer or organization with isolated data and resources |
| Workflow | A defined sequence of steps |
| Workflow execution | One runtime instance of a workflow |
| Trace | A structured timeline of operations during execution |

---

## Document Control

| Field | Value |
| --- | --- |
| Version | 1.0 |
| Status | Design Phase |
| Last Updated | May 2026 |
| Scope | MVP architecture and production direction |
