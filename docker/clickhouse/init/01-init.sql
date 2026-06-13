-- ============================================================
-- ClickHouse IaC bootstrap — runs ONCE on first init
-- (clickhouse-server executes /docker-entrypoint-initdb.d/*.sql).
--
-- Phase 0.5 creates the analytics database + the DLQ sink the Kafka
-- consumer (Phase 4) needs. The full fact/dimension/materialized-view
-- DDL is owned by the OLAP phase and dropped into this same init dir
-- (and re-appliable via `make init-clickhouse`).
-- ============================================================
CREATE DATABASE IF NOT EXISTS payments;

-- Dead-letter sink: Kafka consumer writes events that fail validation/insert.
CREATE TABLE IF NOT EXISTS payments.dead_letter_events
(
    topic       LowCardinality(String),
    raw_payload String CODEC(ZSTD(3)),
    error       String,
    consumer    LowCardinality(String) DEFAULT '',
    failed_at   DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(failed_at)
ORDER BY failed_at
TTL failed_at + INTERVAL 3 MONTH;
