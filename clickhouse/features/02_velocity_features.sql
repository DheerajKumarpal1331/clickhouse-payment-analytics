-- ============================================================
-- Velocity features — 5-minute buckets per customer and per device, the core
-- real-time fraud signals (count/amount/declines/distinct-merchants over short
-- windows). The fraud API reads the last N buckets for an entity to build
-- 5m/1h/24h rolling features without scanning raw facts.
-- ============================================================
CREATE TABLE IF NOT EXISTS payments.agg_velocity_5m
(
    entity_type  Enum8('customer' = 1, 'device' = 2, 'card' = 3),
    entity_id    String,
    bucket       DateTime,
    txn_count    AggregateFunction(count),
    amount_sum   AggregateFunction(sum, Decimal(18, 2)),
    amount_max   AggregateFunction(max, Decimal(18, 2)),
    decline_cnt  AggregateFunction(sumIf, UInt8, UInt8),
    uniq_merch   AggregateFunction(uniq, String),
    fraud_cnt    AggregateFunction(sum, UInt8)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMMDD(bucket)
ORDER BY (entity_type, entity_id, bucket)
TTL bucket + INTERVAL 7 DAY;

CREATE MATERIALIZED VIEW IF NOT EXISTS payments.mv_velocity_customer
TO payments.agg_velocity_5m AS
SELECT CAST('customer', 'Enum8(\'customer\'=1,\'device\'=2,\'card\'=3)') AS entity_type,
       customer_id                            AS entity_id,
       toStartOfFiveMinutes(event_time)       AS bucket,
       countState()                           AS txn_count,
       sumState(amount)                       AS amount_sum,
       maxState(amount)                       AS amount_max,
       sumIfState(toUInt8(1), is_success = 0) AS decline_cnt,
       uniqState(merchant_id)                 AS uniq_merch,
       sumState(fraud_label)                  AS fraud_cnt
FROM payments.fact_transactions
WHERE customer_id != ''
GROUP BY entity_id, bucket;

CREATE MATERIALIZED VIEW IF NOT EXISTS payments.mv_velocity_device
TO payments.agg_velocity_5m AS
SELECT CAST('device', 'Enum8(\'customer\'=1,\'device\'=2,\'card\'=3)') AS entity_type,
       device_id                              AS entity_id,
       toStartOfFiveMinutes(event_time)       AS bucket,
       countState()                           AS txn_count,
       sumState(amount)                       AS amount_sum,
       maxState(amount)                       AS amount_max,
       sumIfState(toUInt8(1), is_success = 0) AS decline_cnt,
       uniqState(merchant_id)                 AS uniq_merch,
       sumState(fraud_label)                  AS fraud_cnt
FROM payments.fact_transactions
WHERE device_id != ''
GROUP BY entity_id, bucket;

-- Finalized rolling-window view (last hour) the scoring path can read per entity.
CREATE VIEW IF NOT EXISTS payments.v_velocity_1h AS
SELECT entity_type,
       entity_id,
       countMerge(txn_count)   AS txn_count_1h,
       sumMerge(amount_sum)    AS amount_sum_1h,
       maxMerge(amount_max)    AS amount_max_1h,
       sumIfMerge(decline_cnt) AS decline_count_1h,
       uniqMerge(uniq_merch)   AS uniq_merchants_1h,
       sumMerge(fraud_cnt)     AS fraud_count_1h
FROM payments.agg_velocity_5m
WHERE bucket >= now() - INTERVAL 1 HOUR
GROUP BY entity_type, entity_id;
