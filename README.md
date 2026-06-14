# Payment Analytics Platform

A production-grade FinTech payment processing & analytics platform modelled on
real Indian payment processors (UPI/NPCI rails, RBI MDR/GST regime, RuPay,
T+1 settlement). Built phase by phase — this repo covers **Phases 0–13**:
OLTP → CDC streaming → ClickHouse OLAP → feature store → fraud ML → unified API
→ live dashboards → orchestration → monitoring → testing → deployment.

A continuous generator streams fresh transactions (and onboards merchants) into
Postgres, so the whole pipeline — Postgres → Kafka → ClickHouse → dashboard —
runs **live** end to end.

## Live dashboards

Five Plotly Dash operator dashboards over the ClickHouse warehouse, auto-refreshing
every few seconds. Business economics (MDR, GST, net settlement) are computed with
standard Indian rates.

| Executive | Merchant |
|---|---|
| ![Executive](docs/screenshots/executive.png) | ![Merchant](docs/screenshots/merchant.png) |
| **Fraud & Risk** | **Settlement** |
| ![Fraud & Risk](docs/screenshots/fraud.png) | ![Settlement](docs/screenshots/settlement.png) |

## Phases in this repo

| Phase | Scope | Location |
|---|---|---|
| **0 — Business Understanding** | Lifecycle docs: payment, merchant, settlement, fraud, support | [`docs/domain/`](docs/domain/) |
| **0.5 — Containerization** | Full Docker Compose stack, IaC, monitoring, Makefile | [`docker/`](docker/), `docker-compose.yml`, `Makefile` |
| **1 — System Design** | HLD · LLD · ERD · DFDs + 6 architecture diagrams (`.drawio`) | [`architecture/`](architecture/) |
| **2 — PostgreSQL OLTP** | 11-domain 3NF schema, indexes, procedures, seed data, tests | [`postgres/`](postgres/) |
| **3 — Synthetic Data Generation** | Merchant/customer/device/transaction generators + **continuous live Postgres feed** | [`data_generator/`](data_generator/) |
| **4 — Kafka Streaming** | 8 event schemas, Postgres→Kafka producers, Kafka→ClickHouse consumers + DLQ | [`kafka/`](kafka/) |
| **5 — ClickHouse OLAP** | 7 dims + 7 facts, materialized views, features, marts, optimization | [`clickhouse/`](clickhouse/) |
| **6 — Feature Store** | Online/offline (PIT) feature pipelines over the warehouse | [`feature_store/`](feature_store/) |
| **7 — Fraud ML** | Velocity feature engineering, training/evaluation, MLflow registry | [`ml/`](ml/) |
| **8 — APIs** | Unified FastAPI service — fraud scoring · merchant · analytics domains + shared layer | [`api/`](api/) |
| **9 — Dashboards** | 5 live auto-refreshing Plotly Dash dashboards (Executive/Merchant/Fraud/Settlement/Support) | [`dashboard/`](dashboard/) |
| **10 — Orchestration** | 8 Airflow DAGs, custom operators/sensors, watermark CDC | [`airflow/`](airflow/) |
| **11 — Monitoring** | Prometheus + Alertmanager + Grafana; Kafka lag / API latency / ClickHouse / Airflow | [`monitoring/`](monitoring/) |
| **12 — Testing** | Unit (ETL/API/ML), integration (PG→Kafka, Kafka→CH, FS→Model), load (5000 ev/s, 100 users) | [`tests/`](tests/) |
| **13 — Deployment** | Full Docker Compose stack + optional Kubernetes (raw manifests + Helm chart) | [`deployment/`](deployment/), [`k8s/`](k8s/), [`helm/`](helm/) |

## Quick start — one command

```bash
cp .env.dev .env          # or: make env ENV=dev
docker compose up -d       # brings up the whole platform (infra + monitoring + dev tools)
make health                # watch containers go healthy
```

On first boot the stack auto-provisions everything (Infrastructure as Code):
Postgres schema + seed, ClickHouse database, Kafka topics, MLflow registry.
Application layers (Kafka pipeline, APIs, dashboard, ML, Airflow) come up under
[compose profiles](docker/README.md) as their phases land:

```bash
docker compose --profile pipeline up -d   # Kafka producers/consumers (Phase 4)
docker compose --profile apps up -d        # unified API + Plotly dashboard
docker compose --profile ml up -d          # feature store + fraud train/serve
docker compose --profile airflow up -d     # orchestration (LocalExecutor)
```

UIs: Plotly Dashboard `:8050` · API docs `:8000/docs` · Grafana `:3000` ·
MLflow `:5000` · Prometheus `:9090` · Airflow `:8082`. The stack is deliberately
lean — Grafana is the single operations pane (Prometheus + ClickHouse datasources)
and ClickHouse SQL is reachable on `:8123`. See
[`deployment/README.md`](deployment/README.md).

### Without Docker (individual phases)

```bash
# Phase 2 — OLTP schema into a running Postgres 16
PGDSN=postgresql://postgres:postgres@localhost:5432/payments postgres/apply.sh

# Phase 3 — synthetic dataset (Parquet)
pip install -r data_generator/requirements.txt
python data_generator/generate.py historical \
    --transactions 100000 --days 30 --merchants 500 --customers 5000 --out ./data
```

## Validation status

- **Phase 1** — all 6 `.drawio` diagrams are well-formed, openable XML.
- **Phase 2** — full schema (121 tables incl. partitions, 200 FKs), procedures and
  triggers load clean on Postgres 16; **all test suites pass** (constraints,
  triggers, procedures, integrity).
- **Phase 3** — generator validated: 106-column transactions, all 6 fraud
  scenarios, and verified temporal patterns (peak hours, weekends, holidays,
  salary days).
- **Phase 10** — all 8 Airflow DAGs parse with zero import errors; watermark CDC
  validated live (201 rows Postgres → ClickHouse, cursor advanced), and the
  data-quality operator runs its contracts across both ClickHouse and Postgres.
  See [`airflow/README.md`](airflow/README.md).
- **Phase 11** — monitoring validated live: `promtool` accepts the alert rules
  and scrape config; Prometheus targets healthy for ClickHouse, Postgres,
  Kafka and the Airflow statsd-exporter; Grafana provisions all three
  datasources (Prometheus/ClickHouse/Postgres health OK) and six dashboards,
  and every Data-Freshness / ML-Monitoring SQL runs against the live schema.
  See [`monitoring/README.md`](monitoring/README.md).
- **Phase 12** — **39 unit tests pass** (ETL/API/ML, no infra); all **9
  integration tests pass** live against the Docker stack (PostgreSQL→Kafka
  round-trip + cursor advance, Kafka→ClickHouse sink + DLQ round-trip, Feature
  Store→Model scoring); load tests validated — Kafka ingest sustained
  **166k events/sec** (target 5000) and **100 concurrent users with 0 failures**
  on the fraud-scoring API. See [`tests/README.md`](tests/README.md).
- **Phase 13** — deployment artifacts validated: the raw manifests render via
  `kubectl kustomize` to **32 resources**, and the Helm chart passes `helm lint`
  and `helm template` (**23 resources**, with the unified-API HPA and the
  external-Secret toggle exercised). See [`deployment/README.md`](deployment/README.md).
