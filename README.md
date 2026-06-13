# Payment Analytics Platform

A production-grade FinTech payment processing & analytics platform modelled on
real Indian payment processors (UPI/NPCI rails, RBI MDR/GST regime, RuPay,
T+1 settlement). Built phase by phase — this repo currently covers **Phases 0–3**.

## Phases in this repo

| Phase | Scope | Location |
|---|---|---|
| **0 — Business Understanding** | Lifecycle docs: payment, merchant, settlement, fraud, support | [`docs/domain/`](docs/domain/) |
| **1 — System Design** | HLD · LLD · ERD · DFDs + 6 architecture diagrams (`.drawio`) | [`architecture/`](architecture/) |
| **2 — PostgreSQL OLTP** | 11-domain 3NF schema, indexes, procedures, seed data, tests | [`postgres/`](postgres/) |
| **3 — Synthetic Data Generation** | Merchant/customer/device/transaction/refund/fraud generators | [`data_generator/`](data_generator/) |

## Quick start

```bash
# Phase 2 — stand up the OLTP database (needs a running Postgres 16)
PGDSN=postgresql://postgres:postgres@localhost:5432/payments postgres/apply.sh
PGDSN=postgresql://postgres:postgres@localhost:5432/payments postgres/tests/run_tests.sh

# Phase 3 — generate a synthetic dataset (Parquet)
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

## Roadmap (later phases)

Streaming (Kafka), OLAP warehouse (ClickHouse), feature store, fraud ML + MLflow,
real-time scoring API, Plotly Dash dashboards, Airflow orchestration, and
Prometheus/Grafana monitoring — to be built in subsequent phases.
