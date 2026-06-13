# Kafka Streaming Platform (Phase 4)

Real-time event pipeline: **PostgreSQL (OLTP) → Kafka → ClickHouse (OLAP)** with
schema validation, a dead-letter queue, and lag/throughput monitoring.

```
postgres ──(CDC watermark poll)──▶ producers ──▶ Kafka topics ──▶ consumers ──(JSONEachRow)──▶ ClickHouse
                                        │                              │
                                        └────────── invalid ──────────┴──▶ <topic>.dlq + dead_letter_events
```

## Layout

| Path | What |
|---|---|
| `schemas/` | 8 Pydantic event contracts, topic registry, validation gate, JSON-Schema export |
| `producers/` | watermark CDC reader (`db_source`), per-topic projection SQL (`queries`), `producer`, CLI |
| `consumers/` | `ch_sink` (stdlib HTTP, JSONEachRow), `consumer` (batch + DLQ + at-least-once), CLI |
| `dlq/` | `dlq_handler` (→ `<topic>.dlq` + `dead_letter_events`), `replay` tool |
| `monitoring/` | Prometheus `metrics`, `consumer_lag` reporter |
| `config.py` | env-driven config |

## Topics (8 + 8 DLQ)

`merchant_events · device_events · transaction_events · refund_events ·
settlement_events · chargeback_events · support_events · fraud_events`
— created by `docker/kafka/create-topics.sh` (Phase 0.5 IaC) with env-driven
partitions / replication / retention; each has a `<topic>.dlq` sibling.

## Design notes

- **Schema validation, two sources, one contract.** Each event model uses
  `extra='allow'`, so the narrow OLTP-CDC payload and the wide gateway payload
  both validate against the same contract.
- **Watermark CDC, no Debezium.** Producers poll each source table past a
  persisted `(watermark, id)` cursor, ordered by `(watermark, id)` so
  same-timestamp rows are neither skipped nor duplicated. The cursor advances
  only after a successful flush. Swap in Debezium/logical decoding for prod.
- **Robust ClickHouse sink.** `INSERT … FORMAT JSONEachRow` with
  `skip_unknown_fields` + `null_as_default` + `best_effort` datetime parsing —
  so the sink tolerates schema width differences and evolution.
- **At-least-once.** Consumers commit offsets only *after* a successful CH
  insert; transient CH errors retry with backoff; exhausted batches go to DLQ
  so the pipeline always advances.
- **DLQ + replay.** Bad events land on `<topic>.dlq` (durable, replayable) and
  in `dead_letter_events` (queryable). `python -m dlq.replay --topic X` re-emits
  fixed events to the source topic.

## Run

```bash
pip install -r kafka/requirements.txt
export KAFKA_BOOTSTRAP=localhost:9092 \
       PG_DSN=postgresql://payments:payments_secret@localhost:5432/payments \
       CH_URL=http://analytics:analytics_secret@localhost:8123 CH_DB=payments

python -m producers.run_producer --all          # Postgres -> Kafka
python -m consumers.run_consumer --all           # Kafka -> ClickHouse
python -m monitoring.consumer_lag --group ch-sink
python -m dlq.replay --topic transaction_events  # after a fix/outage
```

Or containerized: `docker compose --profile pipeline up -d` (see `docker/`).
The consumer's sink tables (`fact_*`, `dim_merchants`) are created by the OLAP
phase; `dead_letter_events` exists from Phase 0.5.

## Tests

```bash
python kafka/tests/test_schemas.py        # schema + registry (no infra)
```
