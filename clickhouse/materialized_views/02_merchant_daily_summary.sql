-- ============================================================
-- merchant_daily_summary — per merchant per day (the workhorse rollup for
-- the Merchant Insights dashboard: volume, success, uniques, revenue, fraud).
-- ============================================================
CREATE TABLE IF NOT EXISTS payments.agg_merchant_daily
(
    merchant_id    LowCardinality(String),
    event_date     Date,
    txn_count      AggregateFunction(count),
    success_count  AggregateFunction(sum, UInt8),
    gross_amount   AggregateFunction(sum, Decimal(18, 2)),
    mdr_amount     AggregateFunction(sum, Decimal(18, 4)),
    avg_amount     AggregateFunction(avg, Decimal(18, 2)),
    max_amount     AggregateFunction(max, Decimal(18, 2)),
    uniq_customers AggregateFunction(uniq, String),
    uniq_devices   AggregateFunction(uniq, String),
    fraud_count    AggregateFunction(sum, UInt8)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (merchant_id, event_date);

CREATE MATERIALIZED VIEW IF NOT EXISTS payments.mv_merchant_daily
TO payments.agg_merchant_daily AS
SELECT merchant_id,
       toDate(event_time)     AS event_date,
       countState()           AS txn_count,
       sumState(is_success)   AS success_count,
       sumState(amount)       AS gross_amount,
       sumState(mdr_amount)   AS mdr_amount,
       avgState(amount)       AS avg_amount,
       maxState(amount)       AS max_amount,
       uniqState(customer_id) AS uniq_customers,
       uniqState(device_id)   AS uniq_devices,
       sumState(fraud_label)  AS fraud_count
FROM payments.fact_transactions
GROUP BY merchant_id, event_date;

CREATE VIEW IF NOT EXISTS payments.merchant_daily_summary AS
SELECT merchant_id,
       event_date,
       countMerge(txn_count)     AS txns,
       sumMerge(success_count)   AS successes,
       sumMerge(gross_amount)    AS gross_amount,
       sumMerge(mdr_amount)      AS revenue,
       avgMerge(avg_amount)      AS avg_amount,
       maxMerge(max_amount)      AS max_amount,
       uniqMerge(uniq_customers) AS uniq_customers,
       uniqMerge(uniq_devices)   AS uniq_devices,
       sumMerge(fraud_count)     AS frauds,
       successes / txns          AS success_rate
FROM payments.agg_merchant_daily
GROUP BY merchant_id, event_date;
