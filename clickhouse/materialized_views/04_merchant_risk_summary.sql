-- ============================================================
-- merchant_risk_summary — per merchant per day risk posture from the txn
-- stream: decline ratio, fraud rate, high-value count. (Chargeback ratio is
-- combined with this in marts/ since an MV reads a single source table.)
-- ============================================================
CREATE TABLE IF NOT EXISTS payments.agg_merchant_risk
(
    merchant_id     LowCardinality(String),
    event_date      Date,
    txn_count       AggregateFunction(count),
    decline_count   AggregateFunction(sumIf, UInt8, UInt8),
    fraud_count     AggregateFunction(sum, UInt8),
    high_value_count AggregateFunction(sumIf, UInt8, UInt8),
    gross_amount    AggregateFunction(sum, Decimal(18, 2)),
    avg_risk_score  AggregateFunction(avg, Float32)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (merchant_id, event_date);

CREATE MATERIALIZED VIEW IF NOT EXISTS payments.mv_merchant_risk
TO payments.agg_merchant_risk AS
SELECT merchant_id,
       toDate(event_time)                          AS event_date,
       countState()                                AS txn_count,
       sumIfState(toUInt8(1), is_success = 0)      AS decline_count,
       sumState(fraud_label)                       AS fraud_count,
       sumIfState(toUInt8(1), amount > 50000)      AS high_value_count,
       sumState(amount)                            AS gross_amount,
       avgState(gateway_risk_score)                AS avg_risk_score
FROM payments.fact_transactions
GROUP BY merchant_id, event_date;

CREATE VIEW IF NOT EXISTS payments.merchant_risk_summary AS
SELECT merchant_id,
       event_date,
       countMerge(txn_count)         AS txns,
       sumIfMerge(decline_count)     AS declines,
       sumMerge(fraud_count)         AS frauds,
       sumIfMerge(high_value_count)  AS high_value_txns,
       sumMerge(gross_amount)        AS gross_amount,
       avgMerge(avg_risk_score)      AS avg_gateway_risk,
       declines / txns               AS decline_ratio,
       frauds / txns                 AS fraud_rate
FROM payments.agg_merchant_risk
GROUP BY merchant_id, event_date;
