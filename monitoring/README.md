# Monitoring (Phase 11)

Prometheus + Alertmanager + Grafana give the platform its observability plane.
Prometheus scrapes every layer, alert rules page on the four things that hurt
most in a payments stack — **Kafka lag, API latency, ClickHouse queries, Airflow
health** — and Grafana turns the time series (plus direct warehouse/OLTP queries)
into three operator-facing dashboards.

## Layout

```
monitoring/
├── prometheus/
│   └── prometheus.yml          # scrape jobs (infra, kafka, postgres, clickhouse, airflow, apps)
├── alerts/
│   ├── alert.rules.yml         # alerting rules grouped by concern
│   └── alertmanager.yml        # routing (critical pages fast, warnings batch)
├── statsd/
│   └── statsd-mapping.yml      # Airflow StatsD -> labeled Prometheus metrics
└── grafana/
    ├── provisioning/
    │   ├── datasources/        # Prometheus + ClickHouse + Postgres
    │   └── dashboards/         # file provider -> /var/lib/grafana/dashboards
    └── dashboards/
        ├── platform-health.json
        ├── data-freshness.json
        ├── ml-monitoring.json
        └── kafka / clickhouse / postgres / docker-health.json
```

## The four monitoring concerns

| Concern | Source | Where it shows up |
|---|---|---|
| **Kafka lag** | `kafka-exporter` (`kafka_consumergroup_lag`) + the pipeline apps' own `consumer_lag` / `events_*_total` | `KafkaConsumerLagHigh`, `KafkaConsumerStalled`, `KafkaDLQGrowing`; Platform Health |
| **API latency** | the unified API's `/metrics` — `api_request_duration_seconds` histogram (labeled by `route`) | `ApiLatencyHighP99`, `FraudApiLatencyHighP99` (route `/score`, <100ms SLA), `ApiErrorRateHigh`; Platform Health, ML Monitoring |
| **ClickHouse queries** | ClickHouse native Prometheus endpoint (`:9363`) — `ClickHouseProfileEvents_*`, `ClickHouseMetrics_*` | `ClickHouseTooManyParts`, `ClickHouseFailedQueries`, `ClickHouseQueriesBacklog`; Platform Health |
| **Airflow health** | Airflow StatsD → `statsd-exporter` → Prometheus (`airflow_*`) | `AirflowSchedulerDown`, `AirflowDagImportErrors`, `AirflowTaskFailuresSpiking`, `AirflowPoolStarving`; Platform Health |

## Dashboards

- **Platform Health** — one pane: targets up, container CPU/mem, Kafka lag by
  topic, API p99 + request rate by service, ClickHouse running queries, Airflow
  scheduler heartbeat. The "is anything on fire?" view.
- **Data Freshness** — warehouse lag (ClickHouse `now() - max(event_time)` per
  fact), OLTP source lag (Postgres `transaction_header`), and OLTP-vs-warehouse
  volume, so a stalled CDC/streaming path is visible as growing lag, not silence.
- **ML Monitoring** — real-time scoring SLA (p50/p95/p99 vs the 100ms budget),
  scoring throughput + error rate, predictions/hour, mean-score drift, risk-level
  mix, active model versions, and observed (labeled) fraud rate.

## Airflow metrics path

Airflow emits StatsD; `statsd-exporter` maps the dotted names to labeled
Prometheus series (`statsd/statsd-mapping.yml`) and Prometheus scrapes it on
`:9102` (job `airflow`). Wired via `x-airflow-common`:

```yaml
AIRFLOW__METRICS__STATSD_ON: "true"
AIRFLOW__METRICS__STATSD_HOST: statsd-exporter
AIRFLOW__METRICS__STATSD_PORT: "9125"
AIRFLOW__METRICS__STATSD_PREFIX: airflow
```

## Run

```bash
docker compose up -d            # prometheus, alertmanager, grafana, statsd-exporter, exporters
docker compose --profile airflow up -d   # also feeds airflow_* metrics
```

UIs: Prometheus `:9090` · Alertmanager `:9093` · Grafana `:3000` (admin/admin) ·
statsd-exporter `:9102`. The ClickHouse and Postgres Grafana datasources read
credentials from compose env, so nothing sensitive is committed; the
`grafana-clickhouse-datasource` plugin installs on Grafana's first boot.

```bash
# validate config without Grafana/Prometheus running:
docker run --rm -v $PWD/monitoring/prometheus:/p -v $PWD/monitoring/alerts:/a \
  prom/prometheus:v2.53.0 promtool check rules /a/alert.rules.yml
```
