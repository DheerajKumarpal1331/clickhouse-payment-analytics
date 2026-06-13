-- ============================================================
-- merchant_monthly_summary — per merchant per month (MoM trends, cohorts).
-- ============================================================
CREATE TABLE IF NOT EXISTS payments.agg_merchant_monthly
(
    merchant_id    LowCardinality(String),
    month          Date,                       -- first of month
    txn_count      AggregateFunction(count),
    success_count  AggregateFunction(sum, UInt8),
    gross_amount   AggregateFunction(sum, Decimal(18, 2)),
    mdr_amount     AggregateFunction(sum, Decimal(18, 4)),
    uniq_customers AggregateFunction(uniq, String),
    fraud_count    AggregateFunction(sum, UInt8)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYear(month)
ORDER BY (merchant_id, month);

CREATE MATERIALIZED VIEW IF NOT EXISTS payments.mv_merchant_monthly
TO payments.agg_merchant_monthly AS
SELECT merchant_id,
       toStartOfMonth(event_time) AS month,
       countState()               AS txn_count,
       sumState(is_success)       AS success_count,
       sumState(amount)           AS gross_amount,
       sumState(mdr_amount)       AS mdr_amount,
       uniqState(customer_id)     AS uniq_customers,
       sumState(fraud_label)      AS fraud_count
FROM payments.fact_transactions
GROUP BY merchant_id, month;

CREATE VIEW IF NOT EXISTS payments.merchant_monthly_summary AS
SELECT merchant_id,
       month,
       countMerge(txn_count)     AS txns,
       sumMerge(success_count)   AS successes,
       sumMerge(gross_amount)    AS gross_amount,
       sumMerge(mdr_amount)      AS revenue,
       uniqMerge(uniq_customers) AS uniq_customers,
       sumMerge(fraud_count)     AS frauds,
       successes / txns          AS success_rate
FROM payments.agg_merchant_monthly
GROUP BY merchant_id, month;
