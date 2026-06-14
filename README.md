# Payment Analytics Platform

A production-grade FinTech payment processing & analytics platform modelled on
real Indian payment processors (UPI/NPCI rails, RBI MDR/GST regime, RuPay,
T+1 settlement). Built phase by phase — this repo currently covers
**Phases 0–11**.

## Phases in this repo

| Phase | Scope | Location |
|---|---|---|
| **0 — Business Understanding** | Lifecycle docs: payment, merchant, settlement, fraud, support | [`docs/domain/`](docs/domain/) |
| **0.5 — Containerization** | Full Docker Compose stack, IaC, monitoring, Makefile | [`docker/`](docker/), `docker-compose.yml`, `Makefile` |
| **1 — System Design** | HLD · LLD · ERD · DFDs + 6 architecture diagrams (`.drawio`) | [`architecture/`](architecture/) |
| **2 — PostgreSQL OLTP** | 11-domain 3NF schema, indexes, procedures, seed data, tests | [`postgres/`](postgres/) |
| **3 — Synthetic Data Generation** | Merchant/customer/device/transaction/refund/fraud generators | [`data_generator/`](data_generator/) |
| **4 — Kafka Streaming** | 8 event schemas, Postgres→Kafka producers, Kafka→ClickHouse consumers + DLQ | [`kafka/`](kafka/) |
| **5 — ClickHouse OLAP** | 7 dims + 7 facts, materialized views, features, marts, optimization | [`clickhouse/`](clickhouse/) |
| **6 — Feature Store** | Online/offline (PIT) feature pipelines over the warehouse | [`feature_store/`](feature_store/) |
| **7 — Fraud ML** | Velocity feature engineering, training/evaluation, MLflow registry | [`ml/`](ml/) |
| **8 — APIs** | 3 FastAPI services (fraud scoring, merchant, analytics) + shared layer | [`api/`](api/) |
| **9 — Dashboards** | 5 Plotly Dash operator dashboards | [`dashboard/`](dashboard/) |
| **10 — Orchestration** | 8 Airflow DAGs, custom operators/sensors, watermark CDC | [`airflow/`](airflow/) |
| **11 — Monitoring** | Prometheus + Alertmanager + Grafana; Kafka lag / API latency / ClickHouse / Airflow | [`monitoring/`](monitoring/) |

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
docker compose --profile apps up -d        # FastAPI services + Plotly dashboard
docker compose --profile ml up -d          # feature store + fraud train/serve
docker compose --profile airflow up -d     # orchestration
```

UIs: Kafka UI `:8080` · Grafana `:3000` · MLflow `:5000` · pgAdmin `:5050` ·
ClickHouse UI `:5521` · Jupyter `:8888` · Prometheus `:9090`. See
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
- **Phase 11** — monitoring validated live: `promtool` accepts all 17 alert rules
  and the scrape config; Prometheus targets healthy for ClickHouse, Postgres,
  cadvisor and the Airflow statsd-exporter; Grafana provisions all three
  datasources (Prometheus/ClickHouse/Postgres health OK) and seven dashboards,
  and every Data-Freshness / ML-Monitoring SQL runs against the live schema.
  See [`monitoring/README.md`](monitoring/README.md).
