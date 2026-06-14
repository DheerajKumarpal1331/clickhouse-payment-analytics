# High-Level Design (HLD)

> System-level design for the ClickHouse Payment Analytics Platform. Read this
> with [`overall_architecture.drawio`](overall_architecture.drawio) open. Domain
> behaviour is in [`../docs/domain/`](../docs/domain); table-level detail is in
> [`LLD.md`](LLD.md).

---

## 1. Problem statement

A payment company (POS + UPI + QR + cards + lending + settlements) is bottlenecked
by a legacy analytical database:

- High-volume aggregations time out; reporting is next-morning, not live.
- Fraud models score on stale features.
- Merchant reporting and settlement monitoring are manual.

**Goal:** an OLTP system of record plus an OLAP analytics plane that handles
**millions of transactions/day**, generates fraud features in near-real-time,
serves a **< 100 ms** fraud score, and powers self-serve dashboards.

---

## 2. Design principles

1. **Separate OLTP from OLAP.** PostgreSQL is the transactional source of truth
   (normalized, ACID); ClickHouse is the analytical mirror (denormalized,
   column-store). Neither is asked to do the other's job.
2. **Stream, don't batch-ETL the hot path.** Events flow OLTP → Kafka → ClickHouse
   continuously; Airflow handles backfill, feature rollups, retraining and DQ —
   not the live ingest.
3. **Compute features once, serve twice.** The same ClickHouse aggregates back
   both offline training (point-in-time) and online scoring (latest value).
4. **Everything observable.** Kafka lag, API latency, CH query time, model
   latency and Airflow health are first-class metrics with alerts.
5. **Schema-on-write at the edge, schema evolution tolerated downstream.**
   Pydantic/JSON-schema validate at the producer; the consumer DLQs bad events
   instead of stalling the partition.

---

## 3. Logical components

| # | Component | Tech | Responsibility |
|---|---|---|---|
| 1 | Payment Gateway API | FastAPI | Auth/capture/refund, merchant & device ops; writes OLTP, emits events |
| 2 | OLTP store | PostgreSQL 16 | System of record, 11 domains, monthly-partitioned transactions |
| 3 | Event bus | Apache Kafka | 8 topics, schema registry, DLQ, retry |
| 4 | OLAP warehouse | ClickHouse 24.3 | Facts + dims + materialized views |
| 5 | Feature store | ClickHouse-backed | Offline (PIT) + online (latest) features |
| 6 | ML / MLOps | XGBoost/LightGBM/RF + MLflow | Train, track, register fraud models |
| 7 | Fraud scoring API | FastAPI | `/score` `/features` `/model-info` `/health`, < 100 ms |
| 8 | Dashboards | Plotly Dash | Executive, Merchant, Fraud, Ops, Settlement, Support |
| 9 | Orchestration | Apache Airflow | ETL, backfill, feature gen, retraining, DQ, monitoring |
| 10 | Observability | Prometheus + Grafana | Metrics, dashboards, alert rules |

> **Implementation note.** The reference deployment consolidates the FastAPI
> services (components 1 & 7 + analytics) into a **single unified API** (`api/main.py`,
> one container, routers per domain) for single-host simplicity — the logical
> boundaries above are preserved as routers and can be split back into separate
> services unchanged. Airflow runs the **LocalExecutor** (no Celery/Redis). A
> continuous generator (`data_generator/live_postgres.py`) streams transactions
> and onboards merchants into Postgres to drive the pipeline live.

---

## 4. Data flow (happy path)

```
POS / app  →  Gateway API  →  PostgreSQL (write)  →  Kafka (publish)
            →  ClickHouse (consume)  →  Materialized Views (auto-aggregate)
            →  Feature Store  →  Fraud Models / Fraud API  →  Dashboards / Users
```

The hot scoring path bypasses batch entirely: the Gateway calls the Fraud API
synchronously, which reads **online features** straight from ClickHouse
aggregates and a model loaded from the MLflow registry.

---

## 5. Non-functional requirements

| Dimension | Target |
|---|---|
| Transaction ingest | 1,000–5,000 events/sec sustained (burst to 10k) |
| Daily volume | 10M+ transactions/day; 3 years history (100M+ rows) |
| Fraud score latency | p99 < 100 ms (excludes issuer round-trip) |
| Dashboard query | p95 < 2 s on 100M-row facts (served from MVs) |
| Data freshness | OLAP within seconds of OLTP for the live stream |
| Availability | Stateless services horizontally scalable; CH replicated, Kafka quorum |
| Durability | Kafka acks=all; CH TTL 18 months on facts; OLTP PITR backups |
| Security | PII hashed/masked at rest; PCI — never store raw PAN; internal-only data network |

---

## 6. Capacity sketch (why ClickHouse)

- 10M txns/day × ~95 columns. A wide MergeTree row compresses well
  (LowCardinality + ZSTD); per-merchant `ORDER BY (merchant_id, event_time)`
  means dashboard scans touch few granules.
- Aggregations (TPV, success rate, fraud features) are **pre-computed** by
  `AggregatingMergeTree` MVs at insert time, so dashboards read megabytes, not
  the full fact.
- A legacy row-store would scan the whole table for these rollups — the exact
  bottleneck this platform removes.

---

## 7. Scaling strategy

| Layer | Single-host (Compose) | Production (K8s) |
|---|---|---|
| APIs | 1 container each | HPA replicas behind a load balancer |
| Kafka | 1 broker (KRaft) | 3-broker quorum, RF=3, partitioned by merchant |
| ClickHouse | 1 node | Sharded (by merchant hash) + replicated cluster, Distributed tables |
| PostgreSQL | 1 node | Primary + read replicas; partition pruning + archival to CH |
| Airflow | LocalExecutor | Celery/Kubernetes executor |

See [`deployment_flow.drawio`](deployment_flow.drawio).

---

## 8. Key trade-offs

- **Denormalization in ClickHouse** — we copy merchant/device attributes onto
  each fact row. Costs storage and update complexity, buys join-free scans. Right
  call for an append-heavy analytical workload.
- **Eventual consistency OLTP→OLAP** — the stream is async, so OLAP lags OLTP by
  seconds. Acceptable for analytics; the Gateway never reads back from CH for
  correctness.
- **Aggregate state in MVs** — `-State`/`-Merge` combinators are powerful but
  require discipline (queries must use the finalized views). Documented in LLD.

---

## 9. Related diagrams

| Concern | File |
|---|---|
| Whole system | [`overall_architecture.drawio`](overall_architecture.drawio) |
| Payment auth + persistence | [`payment_flow.drawio`](payment_flow.drawio) |
| Fraud detection | [`fraud_flow.drawio`](fraud_flow.drawio) |
| Settlement + reconciliation | [`settlement_flow.drawio`](settlement_flow.drawio) |
| Support lifecycle | [`support_flow.drawio`](support_flow.drawio) |
| Deployment topology | [`deployment_flow.drawio`](deployment_flow.drawio) |
