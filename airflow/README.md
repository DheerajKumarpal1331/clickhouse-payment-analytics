# Airflow Orchestration (Phase 10)

Apache Airflow (CeleryExecutor) schedules the platform's batch plane: it keeps
the ClickHouse warehouse (Phase 5) converged from the PostgreSQL OLTP (Phase 2)
via watermark CDC, refreshes the feature store (Phase 6), retrains the fraud
model (Phase 7), and enforces data-quality contracts — the scheduled,
gap-filling complement to the Kafka streaming path (Phase 4).

## DAGs

| DAG | Schedule | What it does |
|---|---|---|
| `merchant_ingestion` | `*/15 * * * *` | CDC `merchant.merchant_master` → `dim_merchants` (SCD via ReplacingMergeTree) |
| `transaction_ingestion` | `*/5 * * * *` | CDC `txn.transaction_header` → `fact_transactions` |
| `refund_ingestion` | `*/10 * * * *` | CDC `refund.refund_requests` → `fact_refunds` |
| `settlement_ingestion` | `@hourly` | CDC `merchant_settlements ⨝ batches` → `fact_settlements` |
| `feature_generation` | `@hourly` | Refresh online snapshot + offline PIT features; compact online table |
| `fraud_training` | `0 2 * * 1` | Gate on labeled data, then dispatch the `ml.train` container; MLflow registers the winner |
| `data_quality` | `@hourly` | Warehouse contracts (volume / completeness / validity / consistency) + OLTP freshness |
| `backfill` | manual | Rewind one source's cursor to a timestamp and re-load a window |

## Layout

```
airflow/
├── dags/         # the 8 DAGs above + common.py (shared defaults, IST, start_date)
├── operators/    # custom operators + shared store clients
│   ├── clients.py              # stdlib-urllib ClickHouse + psycopg2 Postgres + watermark state
│   ├── cdc_queries.py          # per-source OLTP→warehouse projections (external codes, not FKs)
│   ├── pg_to_clickhouse.py     # PostgresToClickHouseOperator — watermark CDC
│   ├── clickhouse_operator.py  # ClickHouseOperator — run SQL / INSERT…SELECT / OPTIMIZE
│   └── data_quality_operator.py# DataQualityOperator — assert SQL-metric contracts
└── sensors/
    ├── postgres_sensor.py      # PostgresRowSensor — fresh rows past the cursor?
    └── clickhouse_sensor.py    # ClickHousePartitionSensor — facts landed for the day?
```

`operators/` and `sensors/` are mounted at `/opt/airflow` and put on `PYTHONPATH`,
so DAGs `from operators import ...` / `from sensors import ...`.

## Design notes

- **Watermark CDC.** Each source has a durable `(wm, id)` cursor (persisted as an
  Airflow Variable, visible in the UI) read in `(wm, id)` order so a same-timestamp
  boundary is never skipped or double-loaded. The cursor advances *only after* the
  slice is inserted, so a mid-run failure replays rather than loses — at-least-once,
  made idempotent by ReplacingMergeTree dimensions and keyed facts.
- **Dependency-light.** ClickHouse over its HTTP interface via stdlib `urllib`
  (the platform's house pattern — see `ml/clickhouse_client.py`, `dashboard/data.py`);
  Postgres via `psycopg2`, already in the Airflow image. No extra drivers required.
- **Sensors save slots.** Ingestion DAGs gate on `PostgresRowSensor` in
  `reschedule` mode with `soft_fail`, so an idle window skips cheaply instead of
  running an empty load or holding a worker slot.
- **Data contracts page, soft checks warn.** A hard breach raises
  `AirflowFailException` (no retry — a contract breach won't fix itself); `warn_only`
  checks log a WARNING (e.g. OLTP freshness, which is expected to be stale in dev).
- **Training is orchestrated, not embedded.** `fraud_training` gates on adequately
  *labeled* data, then dispatches the project's `fraud-training` image
  (`python -m ml.train`) — via the Docker API when the socket is mounted, otherwise
  a logged handoff — so the heavy, differently-dependency'd job stays in its own
  container and the registry promotion lives in MLflow (Phase 7).

## Run

```bash
docker compose --profile airflow up -d      # postgres, redis, init, web/scheduler/worker/triggerer
# UI: http://localhost:8082   (airflow / airflow)
```

DAGs ship paused (`DAGS_ARE_PAUSED_AT_CREATION=true`); unpause from the UI or:

```bash
docker compose exec airflow-scheduler airflow dags unpause transaction_ingestion
# one-shot functional test of a single task (no scheduling):
docker compose exec airflow-scheduler airflow tasks test merchant_ingestion load_merchants
# manual backfill:
docker compose exec airflow-scheduler airflow dags trigger backfill \
  --conf '{"source":"transaction","from_ts":"2024-01-01 00:00:00"}'
```

`CH_URL` / `PG_DSN` are injected by compose; override per-environment with Airflow
Variables `ch_url` / `pg_dsn`, or per-source cursors via `cdc_watermark__<source>`.
