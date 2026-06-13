-- ============================================================
-- device_health_summary — per device per day operational health derived from
-- the transaction stream (success/failure counts, merchants served, last seen).
-- Powers the Operations dashboard's fleet view.
-- ============================================================
CREATE TABLE IF NOT EXISTS payments.agg_device_health
(
    device_id      String,
    event_date     Date,
    txn_count      AggregateFunction(count),
    success_count  AggregateFunction(sum, UInt8),
    failure_count  AggregateFunction(sumIf, UInt8, UInt8),
    uniq_merchants AggregateFunction(uniq, String),
    last_seen      AggregateFunction(max, DateTime),
    gross_amount   AggregateFunction(sum, Decimal(18, 2))
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (device_id, event_date)
TTL event_date + INTERVAL 6 MONTH;

CREATE MATERIALIZED VIEW IF NOT EXISTS payments.mv_device_health
TO payments.agg_device_health AS
SELECT device_id,
       toDate(event_time)                     AS event_date,
       countState()                           AS txn_count,
       sumState(is_success)                   AS success_count,
       sumIfState(toUInt8(1), is_success = 0) AS failure_count,
       uniqState(merchant_id)                 AS uniq_merchants,
       maxState(event_time)                   AS last_seen,
       sumState(amount)                       AS gross_amount
FROM payments.fact_transactions
WHERE device_id != ''
GROUP BY device_id, event_date;

CREATE VIEW IF NOT EXISTS payments.device_health_summary AS
SELECT device_id,
       event_date,
       countMerge(txn_count)     AS txns,
       sumMerge(success_count)   AS successes,
       sumIfMerge(failure_count) AS failures,
       uniqMerge(uniq_merchants) AS merchants_served,
       maxMerge(last_seen)       AS last_seen,
       sumMerge(gross_amount)    AS gross_amount,
       successes / txns          AS success_rate,
       failures / txns           AS failure_rate
FROM payments.agg_device_health
GROUP BY device_id, event_date;
