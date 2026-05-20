# Sutram

**Durable execution and persistent memory infrastructure for production AI workflows.**

---

## TL;DR

**For everyone:** Sutram is like a safety net and memory system for AI applications. When an AI workflow crashes halfway through a complex task, Sutram saves its progress and picks up exactly where it left off — like a video game checkpoint. It also gives AI systems a long-term memory so they remember past conversations, user preferences, and decisions. Every action the AI takes is recorded so you can trace exactly what happened and why.

**For engineers:** Sutram is a production-grade platform for durable workflow orchestration (checkpoint/resume via WAL-backed state machine), hybrid semantic retrieval (pgvector ANN with multi-model versioning, recency decay, and frequency reranking), multi-tenant data isolation (PostgreSQL RLS + application-layer enforcement, ADR-008 compliant pre-filter ANN queries), distributed execution coordination (Redis Streams as event bus, atomic Lua-based distributed locks), and full execution observability (OpenTelemetry, tail-based sampling, per-tenant cost attribution). The entire platform is built on boring technology — Postgres, Redis, Celery, FastAPI — so that the engineering sophistication lives in the product layer, not the infrastructure layer.

---

## Table of Contents

1. [What Sutram Does — Plain English](#what-sutram-does--plain-english)
2. [Why It Exists](#why-it-exists)
3. [How It Works — The Full Picture](#how-it-works--the-full-picture)
4. [Core Capabilities](#core-capabilities)
5. [Architecture](#architecture)
6. [The Technology Stack — For Engineers](#the-technology-stack--for-engineers)
7. [Data Architecture](#data-architecture)
8. [Security and Tenant Isolation](#security-and-tenant-isolation)
9. [Reliability and Recovery](#reliability-and-recovery)
10. [Infrastructure and Deployment](#infrastructure-and-deployment)
11. [Observability](#observability)
12. [Quality Targets](#quality-targets)
13. [API Surface](#api-surface)
14. [Operational Runbooks](#operational-runbooks)
15. [Roadmap](#roadmap)
16. [Glossary](#glossary)

---

## What Sutram Does — Plain English

Imagine you ask an AI assistant to do something complicated — like research a topic, summarize dozens of documents, send emails, and file a report. That task might take ten minutes and involve many steps. Now imagine your internet cuts out halfway through.

Without Sutram, the AI forgets everything and starts over from the beginning.

**With Sutram:**

- The AI saves its progress at every important step, like a video game checkpoint.
- If anything goes wrong — a crash, a network hiccup, a timeout — it resumes exactly where it left off.
- It remembers what it learned from past tasks, so it doesn't ask you the same questions twice.
- Every decision it makes is recorded in plain language, so you can always see what happened and why.

Sutram is not an AI. It is the infrastructure that makes AI applications **reliable, continuous, and trustworthy** — the same way a highway system makes cars useful, even though the highway itself doesn't drive anywhere.

---

## Why It Exists

Production AI workflows fail in three predictable ways. Sutram solves all three.

| Problem | What Happens Without Sutram | What Sutram Does |
|---|---|---|
| **Crashes and interruptions** | A 10-minute workflow crashes at minute 9 and restarts from zero, wasting time and money | Saves progress at every important step; resumes from the last safe point |
| **No memory between sessions** | Every AI session starts blank — the system has no recollection of past interactions or decisions | Gives AI a searchable, long-term memory that persists across sessions |
| **Black-box decisions** | Nobody can explain why the AI did what it did — makes debugging, compliance, and trust impossible | Records every action with full context, timing, and cost attribution |

---

## How It Works — The Full Picture

```
Your Application or AI Agent
        │
        │  "Run this workflow"
        ▼
┌──────────────────────────────────────────────────────┐
│                    API Gateway                        │
│   Authenticates you, checks rate limits, routes      │
│   your request to the right internal service         │
└──────────────────┬───────────────────────────────────┘
                   │
       ┌───────────┼──────────────┐
       │           │              │
       ▼           ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────────┐
│ Workflow │ │  Memory  │ │Observability │
│ Service  │ │ Service  │ │   Service    │
│          │ │          │ │              │
│ Runs     │ │ Stores   │ │ Records      │
│ steps,   │ │ and      │ │ every action │
│ saves    │ │ retrieves│ │ as a trace   │
│ progress │ │ context  │ │ you can      │
│ to DB    │ │ using AI │ │ inspect      │
│          │ │ search   │ │              │
└────┬─────┘ └────┬─────┘ └──────┬───────┘
     │            │              │
     └────────────┴──────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────┐
│                 Data Layer                            │
│  PostgreSQL (state)  │  Redis (speed)  │  S3 (archive)│
└──────────────────────────────────────────────────────┘
```

### The Short Version of Each Component

**API Gateway** — The front door. It checks who you are, how fast you're sending requests, and routes your call to the right place. Nothing else gets through without passing here first.

**Workflow Service** — The engine. It runs your multi-step AI task one step at a time, saves progress after each important step, and knows how to pick up where it left off after a crash. Think of it as the conductor of an orchestra — it doesn't play any instrument, but it makes sure everything happens in the right order and nothing gets lost.

**Memory Service** — The librarian. It stores what the AI has learned — facts, preferences, past outcomes — and retrieves the most relevant memories when the AI needs context. It uses vector search (a technique that finds meaning rather than just matching keywords) to find the right information even when you phrase things differently each time.

**Observability Service** — The black box recorder. Like an aircraft's flight recorder, it captures every step, decision, duration, and cost so you can always understand what happened during an AI workflow. Useful for debugging, compliance, and building trust.

---

## Core Capabilities

### 1. Durable Workflow Execution

Sutram runs AI workflows as resumable state machines. Each execution is tracked at every step.

**What this means in practice:**

- A workflow that calls an LLM, queries a database, and sends an email can crash at any point and resume from the last completed step — not the beginning.
- The system saves a "checkpoint" before expensive operations like LLM calls. If the call succeeds, great. If it crashes, the next worker picks up and retries only that step.
- Cost, time, and resource limits are enforced automatically. A runaway workflow cannot accidentally rack up a $500 LLM bill.

**Execution lifecycle:**

```
PENDING → RUNNING → COMPLETED
              │
              └→ PAUSED (recoverable error)
                    └→ RUNNING (on resume)
                    └→ CANCELLED
              └→ FAILED (unrecoverable)
```

**For engineers:** Checkpoint creation uses a write-ahead log (WAL) pattern — WAL append → atomic DB write → WAL commit. Recovery is handled by a background heartbeat monitor that detects stale executions and re-enqueues them to Celery. Distributed locking (atomic Lua, Redis `SET NX EX`) prevents split-brain: two workers can never simultaneously advance the same execution. The state machine rejects all invalid transitions (`InvalidTransitionError`), making status corruption impossible through normal code paths.

### 2. Persistent Semantic Memory

Sutram gives AI systems a long-term memory that persists across sessions and is retrieved by meaning, not just keywords.

**Three memory types:**

| Type | In Plain English | Technical Use |
|---|---|---|
| **Episodic** | "What happened" | "Last Tuesday's invoice workflow failed at the validation step" |
| **Semantic** | "What is known" | "This customer always wants results in bullet points, not paragraphs" |
| **Procedural** | "How to do it" | "For expense reports, always validate line items before totalling" |

**How retrieval works (3 stages):**

1. **Hot cache** — Check Redis first. If someone searched for this recently, return the cached result instantly (under 5ms).
2. **Vector search** — If not cached, search PostgreSQL using pgvector. Find the 50 most similar memories by meaning using approximate nearest-neighbor (ANN) search. The tenant filter is applied *before* the similarity sort — a critical security constraint (ADR-008).
3. **Reranking** — Score the top 50 candidates using: `similarity × 0.6 + recency × 0.3 + frequency × 0.1`. Return the top K. More recently accessed and frequently used memories rank higher.

**For engineers:** ANN queries use `ivfflat` cosine distance on pgvector. ADR-007 enforces embedding model versioning: every row stores `embedding_model`, and during provider migrations, queries group candidates by model, embed the query with the same model per group, and merge before reranking. The frequency term is capped at `min(log(access_count+1), 2.0)` to prevent high-access items from overwhelming the similarity signal. Access stats are updated post-response via FastAPI `BackgroundTasks` with a fresh DB session.

### 3. Execution Observability

Every workflow execution produces structured traces, metrics, and audit records.

**What gets recorded:**
- How long each step took
- How much each LLM call cost
- How many retries occurred
- Which checkpoints were created
- What errors happened and why
- Per-tenant cost over time (this is the billing signal)

**For engineers:** The observability service consumes events from Redis Streams (durable, consumer groups, replayable — not pub/sub). Tail-based sampling: a trace is buffered until completion, then a decision is made — keep 100% of failures and slow executions (>30s), sample the rest at 10%. This gives full diagnostic coverage at a fraction of the storage cost.

---

## Architecture

### Principles (What Every Engineering Decision Follows)

| Principle | Plain English | Technical Meaning |
|---|---|---|
| **Durability first** | Never say "done" until the data is actually saved | State is persisted before success is acknowledged |
| **Fail safe** | When uncertain, stop and wait — don't proceed and hope | Recoverable errors move to PAUSED, not FAILED |
| **Observable by design** | Explain everything that happened | Traces, metrics, and audit records are first-class outputs |
| **Tenant isolation** | Customer A can never see Customer B's data | Row-level security, application-layer scoping, key-namespaced Redis |
| **Boring technology** | Use proven tools; build interesting things on top | Postgres + Redis + Celery + FastAPI — nothing exotic |
| **Stateless services** | Any instance of a service can handle any request | State lives in the data layer, not in memory |

### System Layout

```
services/
├── api-gateway/           # Auth, rate limiting, routing
├── workflow-service/      # Execution engine, checkpoints, recovery, webhooks
├── memory-service/        # Vector search, compression, archival
└── observability-service/ # Traces, metrics, audit log

packages/
└── core/                  # Shared: models, events, Redis streams, distributed lock,
                           #         auth middleware, embedding registry, DB session

infra/
├── docker-compose.yml     # Full stack
├── postgres/init.sql      # pgvector + RLS setup
├── pgbouncer/             # Connection pooling (prevents Postgres saturation)
├── redis/redis.conf       # AOF persistence, 4 logical DBs
└── grafana/               # Pre-built dashboards

sdk/                       # pip install sutram-sdk
```

### Inter-Service Communication

Services communicate two ways:

1. **HTTP (synchronous)** — When one service needs a response. Gateway proxies to workflow-service or memory-service. Workflow-service calls memory-service during step execution.
2. **Redis Streams (asynchronous)** — When a service needs to emit an event that doesn't need a reply. Workflow-service publishes execution events; observability-service consumes them. Redis Streams (not pub/sub) ensures messages are durable — if the consumer is down, messages queue up and are processed when it recovers.

**Internal auth:** Every service-to-service call carries `X-Internal-Token` (constant-time HMAC comparison). Tenant context is carried via `X-Tenant-ID` header, set by the gateway after JWT verification.

---

## The Technology Stack — For Engineers

This is not an exhaustive list — it's the decisions that are interesting.

### Why PostgreSQL for Everything (Including Vectors)

A separate vector database (Pinecone, Weaviate) adds an operational dependency, a billing relationship, and a failure domain. pgvector gives us ANN search with `ivfflat` indexes inside the same Postgres instance that already holds workflow state. At MVP scale this is identical in retrieval performance. When we need to cross 10M vectors per tenant, we add a dedicated vector DB — we don't need to today.

### Why Redis Streams (Not Pub/Sub)

Redis pub/sub drops messages when no consumer is subscribed. If the observability service restarts mid-execution, every span event during that window is silently lost. Redis Streams persist messages regardless of consumer state, support consumer groups (exactly-once per group), and support replay from any offset. This is the right trade-off for a platform where observability is a product feature.

### Why PgBouncer

With 5+ service types × multiple pods × SQLAlchemy connection pools, you exhaust Postgres `max_connections` before a single user request arrives. PgBouncer in transaction-pooling mode multiplexes thousands of application connections onto a fixed pool of server connections. One Docker Compose service, zero code changes.

**Critical note:** Transaction-pooling mode means `SET` commands don't persist across transactions. Row-level security context must use `SET LOCAL app.current_tenant_id` (not `SET`) so it's scoped to the current transaction and reset when PgBouncer recycles the connection.

### Why Celery (Not Temporal or Prefect)

Temporal and Prefect are excellent. They're also heavy dependencies with their own servers, SDKs, and operational surface. Celery with Redis is something every Python engineer already knows, runs in Docker Compose in 30 seconds, and scales from a single worker to hundreds. The workflow durability is implemented at the application layer (checkpoints, WAL, distributed locks) — we don't need the framework to own it.

### Why Atomic Lua for Distributed Locking

The naive pattern for releasing a lock is `GET` then `DEL`. Between those two commands, another process can acquire the key — a classic TOCTOU race. The correct approach is a Lua script that runs as a single atomic Redis command:

```lua
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
```

This is what protects against two workers simultaneously advancing the same execution state machine.

### Why AES-GCM for Webhook Secrets (Not SHA-256)

Webhook delivery requires signing the payload with `HMAC-SHA256(secret, payload)`. SHA-256 is one-way — you cannot derive a signing key from a hash. Webhook secrets are stored AES-256-GCM encrypted (with a KMS-managed key), decrypted at delivery time, and the raw secret is shown to the user exactly once at registration. This is a subtle but important correctness distinction from the common "hash-and-compare" API key pattern.

---

## Data Architecture

Sutram uses different storage systems for different access patterns.

| Data | Storage | Why |
|---|---|---|
| Workflow state, checkpoints, tenants | PostgreSQL | ACID transactions — cannot lose this |
| Memory embeddings | PostgreSQL + pgvector | ANN search co-located with the data it describes |
| Hot query cache, embedding cache | Redis DB 0 | Sub-5ms lookup |
| Distributed locks | Redis DB 2 | Isolated keyspace, no collision with cache |
| Rate limiting counters | Redis DB 3 | Isolated keyspace |
| Event streams | Redis DB 1 | Durable, consumer groups, replayable |
| Execution traces | TimescaleDB | Time-series compression and hypertable partitioning |
| Compressed memory archives | S3 | Low-cost, indefinite retention |

### Database Ownership

Each service owns its own tables. No cross-service foreign keys. Consistency at the service boundary is application-level, not database-level.

| Service | Owns |
|---|---|
| workflow-service | tenants, workflows, workflow_executions, checkpoints, webhook_subscriptions, webhook_deliveries |
| memory-service | memory_items, memory_summaries |
| observability-service | execution_traces, audit_log |

### Tenant Isolation at the Database Layer

Every table has a `tenant_id` column. Row-level security policies enforce that queries only see rows matching the current session's tenant:

```sql
CREATE POLICY tenant_isolation ON workflow_executions
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
```

The `true` argument is `missing_ok` — it returns NULL instead of raising an error when the GUC isn't set, preventing every unauthenticated background job from crashing with a Postgres error.

---

## Security and Tenant Isolation

Security is built in layers. Breaking one layer does not break the system.

| Layer | What It Does |
|---|---|
| **Network** | VPC isolation, private subnets, WAF, DDoS protection |
| **Authentication** | JWT (RS256), OAuth 2.0, API keys |
| **Authorization** | RBAC, tenant-scoped permissions |
| **Data encryption** | TLS 1.3 in transit, AES-256 at rest |
| **Tenant isolation** | Row-level security + application-layer scoping |
| **Internal auth** | `X-Internal-Token` constant-time HMAC comparison on all service-to-service calls |
| **Secrets** | Webhook secrets AES-GCM encrypted; API keys SHA-256 hashed; raw values never stored |
| **Audit trail** | Append-only audit log, `INSERT`-only DB role — cannot be tampered with after the fact |

---

## Reliability and Recovery

Sutram assumes failures will happen and designs for safe recovery rather than trying to prevent all failures.

**What can fail and what happens:**

| Failure | Sutram's Response |
|---|---|
| Worker process crash mid-execution | Heartbeat goes stale in <5 min; recovery handler re-enqueues; Celery resumes from latest checkpoint |
| Database primary failure | RDS promotes standby; services reconnect; checkpoint state intact |
| LLM API timeout or 5xx | Step retried up to N times with exponential backoff; execution paused if retries exhausted |
| Redis restart | Streams are persisted via AOF; consumer groups resume from last ACK'd offset |
| Network partition | Execution pauses; state preserved; resumes when connectivity returns |

**Split-brain prevention:** Before any state mutation, the executor acquires `execution:{id}:lock` in Redis. If the recovery handler tries to re-enqueue a stuck execution while the original worker is just slow (not dead), it gets `LockAcquisitionError` and skips — no double-execution. The lock is released *after* re-enqueueing — not before — so the new worker doesn't race against the recovery handler's still-held lock.

**Recovery targets:**

| Metric | Target |
|---|---|
| Availability | 99.9% |
| Durability (no data loss) | 99.99% |
| Stuck execution detection | <5 minutes |
| Checkpoint resume | <10 seconds |
| Pod crash recovery | <1 minute |
| DB failover | <5 minutes |

---

## Infrastructure and Deployment

### Local Development

```bash
make dev         # Start full stack: Postgres, PgBouncer, Redis, all services, Grafana
make seed        # Create dev tenant, API key, example workflow
make test        # Run all tests against isolated test DBs
make lint        # ruff check + format check
make typecheck   # mypy
```

### Production Topology (Single Region MVP)

```
AWS US-EAST-1
  ALB (Load Balancer)
    ECS Fargate
      api-gateway          (3 pods)
      workflow-service     (5 pods)
      workflow-worker      (10 pods, Celery)
      memory-service       (3 pods)
      observability-service(2 pods)

  Data Layer
    RDS PostgreSQL Multi-AZ (r6g.xlarge, 2 read replicas)
    PgBouncer (transaction pooling, max 500 client connections)
    ElastiCache Redis (cluster mode, AOF enabled)
    TimescaleDB (30-day hot, archive to S3)
    S3 (memory archives, trace cold storage)
```

### CI/CD Pipeline

```
Developer Commit
  → GitHub Actions
  → Per-service matrix: ruff + mypy + unit tests + integration tests
  → Schemathesis contract tests (fuzz every API endpoint)
  → Security scan (SAST + dependency check)
  → Build Docker images → push to ECR
  → Deploy to staging (auto)
  → End-to-end tests on staging
  → Manual approval gate
  → Blue-green production deploy
```

---

## Observability

Sutram treats observability as a product feature, not an afterthought.

**What is automatically captured for every workflow execution:**

- Full OpenTelemetry trace (every step as a span)
- LLM call count and cost per step
- Checkpoint creation events
- Memory reads and writes with latency
- Error and retry events
- Tenant-level cost accumulation (billing signal)

**Tail-based trace sampling:**

Storing every span from every execution is expensive. Instead, Sutram buffers each trace until completion, then decides:
- **Always keep:** any trace with a failure or duration >30s
- **Sample at 10%:** fast, successful traces

This means 100% of problems are captured at roughly 10% of the storage cost.

**Pre-built Grafana dashboards:**
- Execution health (error rate, latency, active executions)
- Memory performance (retrieval latency, cache hit rate, storage growth)
- Cost attribution per tenant per day

---

## Quality Targets

| Metric | Target |
|---|---|
| API response time | P95 < 500ms |
| Memory retrieval | P95 < 200ms |
| Workflow start | P95 < 2s |
| Checkpoint creation | P95 < 100ms |
| Throughput | 1,000 req/s per region |
| Concurrent executions | 10,000 per region |
| Execution success rate | >99% |
| Trace coverage | 100% of executions |

---

## API Surface

### Workflow Management

```http
POST   /v1/workflows
GET    /v1/workflows/{workflow_id}
POST   /v1/workflows/{workflow_id}/execute
GET    /v1/executions/{execution_id}
GET    /v1/executions/{execution_id}/stream   (Server-Sent Events, real-time)
POST   /v1/executions/{execution_id}/pause
POST   /v1/executions/{execution_id}/resume
POST   /v1/executions/{execution_id}/cancel
```

### Memory Operations

```http
POST   /v1/memory/items              (single or batch)
GET    /v1/memory/items/{item_id}
DELETE /v1/memory/items/{item_id}    (GDPR forget)
POST   /v1/memory/search
```

### Observability

```http
GET    /v1/traces/{execution_id}
GET    /v1/metrics?start={ts}&end={ts}&metric={name}
GET    /v1/audit-logs?start={ts}&end={ts}
```

### Webhooks

```http
POST   /v1/webhooks                  (register; secret shown once)
GET    /v1/webhooks
DELETE /v1/webhooks/{webhook_id}
```

### Python SDK (Coming)

```python
import sutram

client = sutram.Client(api_key="sk-...")

@sutram.workflow
class ResearchAgent:
    @sutram.step(checkpoint_before=True, retry=sutram.RetryPolicy(max_attempts=3))
    async def fetch_sources(self, ctx, query: str) -> list[str]:
        return await ctx.tools.web_search(query)

    @sutram.step(checkpoint_before=True)
    async def summarize(self, ctx, sources: list[str]) -> str:
        prior = await ctx.memory.search("prior research")
        return await ctx.llm.complete(f"Summarize {sources}, context: {prior}")

# Execute
wf = await client.workflows.create(ResearchAgent)
execution = await client.workflows.execute(wf.id, inputs={"query": "quantum computing"})

# Stream real-time progress
async for event in client.executions.stream(execution.id):
    print(event.step_name, event.status)

result = await execution.wait()
```

---

## Operational Runbooks

### Start the Platform Locally

```bash
make dev          # Starts everything
make seed         # Creates a dev tenant and seeds example data
# Visit http://localhost:3000 for Grafana dashboards
```

### High Error Rate

1. Check Grafana → Execution Health dashboard
2. `docker logs workflow-service` — identify the failing step
3. Check if the error correlates with a recent deploy
4. If yes: roll back (`kubectl rollout undo deployment/workflow-service`)
5. If no: check LLM provider status, database health, Redis lag

### Stuck Executions

The recovery handler runs every 60 seconds and re-enqueues any execution whose heartbeat is older than 5 minutes. If executions are piling up in RUNNING state:

1. Check worker pod count and queue depth in Grafana
2. Scale workers if queue is backed up
3. If single execution is stuck: inspect its last checkpoint and error message via `GET /v1/executions/{id}`

---

## Roadmap

### Implemented (Plans 1–3)

- ✅ `packages/core` — shared domain models, Redis Streams, distributed lock, embedding registry, auth middleware
- ✅ `workflow-service` — full execution engine with checkpoint/resume, Celery workers, recovery handler, webhooks, SSE
- ✅ `memory-service` — pgvector ANN search, multi-model versioning, reranker, Redis cache, LLM compression, S3 archival

### In Progress (Plans 4–6)

- 🔧 `api-gateway` — JWT verification, rate limiting, routing, Schemathesis contract tests
- 🔧 `observability-service` — Redis Streams consumer, tail-based sampling, Prometheus metrics, audit log
- 🔧 `sutram-sdk` — decorator API, typed async/sync client, PyPI publish, GitHub Actions CI

### Post-MVP

- Web console for workflow monitoring
- Human review queues for paused workflows
- Enterprise SSO
- Multi-region disaster recovery
- Advanced cost optimization

---

## Glossary

| Term | Plain English | Technical Definition |
|---|---|---|
| **Checkpoint** | A save point | A durable snapshot of workflow state written before expensive operations, used for crash recovery |
| **Durable execution** | Crash-proof task running | Execution that checkpoints state and resumes after failures without restarting from zero |
| **Episodic memory** | "What happened" | Structured records of specific past events and execution outcomes |
| **Semantic memory** | "What is known" | Facts, preferences, and contextual knowledge retrievable by meaning, not keyword |
| **Procedural memory** | "How to do it" | Step-by-step process knowledge and operational patterns |
| **Execution context** | The task's working state | Runtime variables, cost accumulation, step index, and metadata passed between steps |
| **Tenant** | A customer account | An organization with fully isolated data, resources, and configuration |
| **Workflow** | A multi-step task definition | A named, versioned sequence of steps that Sutram executes durably |
| **Execution** | One run of a workflow | A single runtime instance of a workflow with its own state, checkpoints, and trace |
| **Trace** | The flight recorder | A structured timeline of every operation, timing, and cost during one execution |
| **ANN search** | Smart similarity search | Approximate nearest-neighbor search — finds semantically similar items fast using vector math |
| **pgvector** | Postgres for AI search | A PostgreSQL extension that enables fast similarity search on embedding vectors |
| **Distributed lock** | "I have the key" | A Redis-based mechanism ensuring only one worker can advance an execution at a time |
| **WAL** | Write-ahead log | Writing an intent to a durable log before executing the action — guarantees recovery if mid-write crash |

---

## Document Control

| Field | Value |
|---|---|
| Version | 2.0 |
| Status | Active Development |
| Last Updated | May 2026 |
| Scope | MVP architecture, production direction, implementation status |
