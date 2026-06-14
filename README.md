# Payment Analytics Platform

A production-grade FinTech payment processing & analytics platform modelled on
real Indian payment processors (UPI/NPCI rails, RBI MDR/GST regime, RuPay,
T+1 settlement). Built phase by phase — this repo currently covers
**Phases 0–3 + 0.5 (containerization)**.

## Phases in this repo

| Phase | Scope | Location |
|---|---|---|
| **0 — Business Understanding** | Lifecycle docs: payment, merchant, settlement, fraud, support | [`docs/domain/`](docs/domain/) |
| **0.5 — Containerization** | Full Docker Compose stack, IaC, monitoring, Makefile | [`docker/`](docker/), `docker-compose.yml`, `Makefile` |
| **1 — System Design** | HLD · LLD · ERD · DFDs + 6 architecture diagrams (`.drawio`) | [`architecture/`](architecture/) |
| **2 — PostgreSQL OLTP** | 11-domain 3NF schema, indexes, procedures, seed data, tests | [`postgres/`](postgres/) |
| **3 — Synthetic Data Generation** | Merchant/customer/device/transaction/refund/fraud generators | [`data_generator/`](data_generator/) |

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

## Roadmap (later phases)

Streaming (Kafka), OLAP warehouse (ClickHouse), feature store, fraud ML + MLflow,
real-time scoring API, Plotly Dash dashboards, Airflow orchestration, and
Prometheus/Grafana monitoring — to be built in subsequent phases.
