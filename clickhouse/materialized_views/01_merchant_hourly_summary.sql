-- ============================================================
-- merchant_hourly_summary — per merchant per hour.
-- Pattern (used by all MVs): AggregatingMergeTree target holding -State
-- partial aggregates, an MV that writes them at insert time, and a finalized
-- `v_*` view that applies -Merge. Dashboards query the v_* view, never the agg.
-- ============================================================
CREATE TABLE IF NOT EXISTS payments.agg_merchant_hourly
(
    merchant_id   LowCardinality(String),
    event_hour    DateTime,
    txn_count     AggregateFunction(count),
    success_count AggregateFunction(sum, UInt8),
    gross_amount  AggregateFunction(sum, Decimal(18, 2)),
    fraud_count   AggregateFunction(sum, UInt8)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMMDD(event_hour)
ORDER BY (merchant_id, event_hour)
TTL event_hour + INTERVAL 3 MONTH;

CREATE MATERIALIZED VIEW IF NOT EXISTS payments.mv_merchant_hourly
TO payments.agg_merchant_hourly AS
SELECT merchant_id,
       toStartOfHour(event_time) AS event_hour,
       countState()              AS txn_count,
       sumState(is_success)      AS success_count,
       sumState(amount)          AS gross_amount,
       sumState(fraud_label)     AS fraud_count
FROM payments.fact_transactions
GROUP BY merchant_id, event_hour;

CREATE VIEW IF NOT EXISTS payments.merchant_hourly_summary AS
SELECT merchant_id,
       event_hour,
       countMerge(txn_count)   AS txns,
       sumMerge(success_count) AS successes,
       sumMerge(gross_amount)  AS gross_amount,
       sumMerge(fraud_count)   AS frauds,
       successes / txns        AS success_rate
FROM payments.agg_merchant_hourly
GROUP BY merchant_id, event_hour;
