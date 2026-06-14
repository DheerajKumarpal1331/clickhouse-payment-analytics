# Containerization (Phase 0.5)

Every component runs as an independent container. The whole platform comes up
with **one command**:

```bash
cp .env.dev .env          # or: make env ENV=dev
docker compose up -d       # infra + monitoring + dev tools (all runnable today)
```

Application layers that are delivered in later phases are gated behind **compose
profiles**, so the default `up -d` always succeeds on a fresh checkout:

| Command | Adds |
|---|---|
| `docker compose up -d` | postgres, clickhouse, zookeeper, kafka(+init,+ui), mlflow, prometheus, grafana, alertmanager, node-exporter, cadvisor, kafka/postgres exporters, pgadmin, clickhouse-ui, jupyter |
| `--profile pipeline` | kafka-producer, kafka-consumer (Phase 4) |
| `--profile apps` | merchant-api, analytics-api, fraud-api, plotly-dashboard |
| `--profile ml` | feature-store, fraud-training, fraud-serving |
| `--profile airflow` | redis, airflow-init, webserver, scheduler, worker, triggerer |

`make up` / `make up-all` / `make down` / `make logs` / `make test` /
`make seed-data` wrap these (see the root `Makefile`).

## Service map & ports

| Service | Image / build | Host port | Profile |
|---|---|---|---|
| postgres | postgres:16 | 5432 | default |
| clickhouse | clickhouse-server:24.3 | 8123 / 9000 | default |
| zookeeper / kafka | confluent cp 7.6 | 2181 / 9092 | default |
| kafka-ui | provectuslabs/kafka-ui | 8080 | default |
| mlflow | build `docker/mlflow` | 5000 | default |
| prometheus / alertmanager | prom images | 9090 / 9093 | default |
| grafana | grafana 11 | 3000 | default |
| node-exporter / cadvisor | prom / google | 9100 / 8085 | default |
| kafka-exporter / postgres-exporter | community | 9308 / 9187 | default |
| statsd-exporter | prom (Airflow bridge) | 9102 | default |
| pgadmin / clickhouse-ui / jupyter | dev tools | 5050 / 5521 / 8888 | default |
| merchant/analytics/fraud-api | build `docker/api` | 8001-8003 | apps |
| plotly-dashboard | build `docker/dashboard` | 8050 | apps |
| airflow-web | apache/airflow | 8082 | airflow |

## Infrastructure as Code (auto-created on first boot)

- **PostgreSQL** — `docker/postgres/init/00-init.sh` creates the `mlflow` and
  `airflow` side-databases, then applies the Phase-2 OLTP schema in order
  (`ddl → indexes → procedures → seed`). Databases, schemas, tables, indexes,
  seed data: all present after `up -d`.
- **ClickHouse** — `docker/clickhouse/init/01-init.sql` creates the `payments`
  database and the DLQ sink; the full fact/dimension/MV DDL drops into the same
  init dir in the OLAP phase (re-appliable via `make init-clickhouse`).
- **Kafka** — `kafka-init` runs `docker/kafka/create-topics.sh`: the 8 domain
  topics + 8 `.dlq` siblings, with env-driven partitions / replication /
  retention.
- **MLflow** — the tracking server auto-migrates the experiment-tracking and
  model-registry tables into the `mlflow` Postgres database on startup.

## Per-service contract

Each buildable service under `docker/<svc>/` carries a `Dockerfile`,
`requirements.txt`, `.env.example`, a container `HEALTHCHECK`, and a
`startup.sh` entrypoint, per the Phase 0.5 requirement.

## Monitoring

The full observability stack lives under [`monitoring/`](../monitoring/) (Phase 11):
Prometheus scrape config, alert rules, Alertmanager routing, the Airflow StatsD
mapping, and Grafana provisioning + dashboards. Prometheus scrapes node-exporter,
cadvisor, kafka-exporter, postgres-exporter, ClickHouse's native endpoint, the
Airflow statsd-exporter, and (under profiles) the pipeline/API `/metrics`.
Grafana is provisioned with Prometheus + ClickHouse + Postgres datasources and
seven dashboards (Platform Health, Data Freshness, ML Monitoring, plus Docker
Health, Kafka, PostgreSQL, ClickHouse). See [`monitoring/README.md`](../monitoring/README.md).
