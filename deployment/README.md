# Deployment Guide

## Local / single host (Docker Compose)

```bash
git clone <repo> && cd clickhouse-payment-analytics
cp .env.dev .env          # pick environment: .env.dev | .env.qa | .env.prod
docker compose up -d      # core platform
make health               # watch containers become healthy
```

First boot performs all Infrastructure-as-Code automatically (Postgres schema +
seed, ClickHouse database + DLQ, Kafka topics, MLflow registry). Bring up later
layers as their phases land:

```bash
docker compose --profile pipeline up -d   # Kafka producers/consumers
docker compose --profile apps up -d       # APIs + dashboard
docker compose --profile ml up -d         # feature store + train/serve
docker compose --profile airflow up -d    # orchestration
```

### UIs

| URL | What |
|---|---|
| http://localhost:8080 | Kafka UI |
| http://localhost:3000 | Grafana (admin/admin) |
| http://localhost:5000 | MLflow |
| http://localhost:5050 | pgAdmin |
| http://localhost:5521 | ClickHouse UI |
| http://localhost:8888 | JupyterLab (token: `payments`) |
| http://localhost:9090 | Prometheus |

## Environments

`.env.dev` / `.env.qa` / `.env.prod` differ in credentials, Kafka
replication/retention, log level, and artifact store. `cp .env.<env> .env`
before `up`. **Never commit a real `.env`** — it is gitignored; prod secrets
come from a secrets manager, not the file.

## Production notes (Kubernetes)

Compose is for local/QA. For production this maps to Kubernetes:

- **Stateless** (APIs, dashboard, producers/consumers) → Deployments + HPA
  behind a Service/Ingress.
- **Kafka** → 3-broker StatefulSet (or managed MSK/Confluent Cloud);
  `KAFKA_TOPIC_REPLICATION=3`, 12+ partitions on `transaction_events`.
- **ClickHouse** → sharded + replicated cluster (Altinity operator),
  `Distributed` tables over shards keyed by `cityHash64(merchant_id)`.
- **PostgreSQL** → managed (RDS/Cloud SQL) primary + read replicas; old txn
  partitions archived to ClickHouse.
- **Airflow** → KubernetesExecutor; **MLflow** artifacts → S3/GCS.
- **Observability** → Prometheus Operator + Grafana; Alertmanager → PagerDuty/Slack.

A Helm chart / kustomize overlays per environment are the next step; the
compose service definitions and env files are the source of truth they derive
from.

## Operations

| Task | Command |
|---|---|
| Tail a service | `make logs S=clickhouse` |
| Health snapshot | `make health` |
| Run tests | `make test` |
| Seed data | `make seed-data` |
| psql / clickhouse shell | `make psql` / `make ch` |
| Full reset (drops volumes) | `make clean` |
