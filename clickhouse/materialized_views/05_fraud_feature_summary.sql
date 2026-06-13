-- ============================================================
-- fraud_feature_summary — per merchant per hour fraud-signal aggregates
-- (count, amount distribution, declines, distinct cards/devices, international).
-- Backs the fraud dashboard and seeds merchant-level model features.
-- ============================================================
CREATE TABLE IF NOT EXISTS payments.agg_fraud_features
(
    merchant_id    LowCardinality(String),
    event_hour     DateTime,
    txn_count      AggregateFunction(count),
    amount_avg     AggregateFunction(avg, Decimal(18, 2)),
    amount_max     AggregateFunction(max, Decimal(18, 2)),
    decline_count  AggregateFunction(sumIf, UInt8, UInt8),
    fraud_count    AggregateFunction(sum, UInt8),
    uniq_cards     AggregateFunction(uniq, String),
    uniq_devices   AggregateFunction(uniq, String),
    intl_count     AggregateFunction(sum, UInt8)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMMDD(event_hour)
ORDER BY (merchant_id, event_hour)
TTL event_hour + INTERVAL 3 MONTH;

CREATE MATERIALIZED VIEW IF NOT EXISTS payments.mv_fraud_features
TO payments.agg_fraud_features AS
SELECT merchant_id,
       toStartOfHour(event_time)              AS event_hour,
       countState()                           AS txn_count,
       avgState(amount)                       AS amount_avg,
       maxState(amount)                       AS amount_max,
       sumIfState(toUInt8(1), is_success = 0) AS decline_count,
       sumState(fraud_label)                  AS fraud_count,
       uniqState(card_hash)                   AS uniq_cards,
       uniqState(device_id)                   AS uniq_devices,
       sumState(is_international)              AS intl_count
FROM payments.fact_transactions
GROUP BY merchant_id, event_hour;

CREATE VIEW IF NOT EXISTS payments.fraud_feature_summary AS
SELECT merchant_id,
       event_hour,
       countMerge(txn_count)     AS txns,
       avgMerge(amount_avg)      AS amount_avg,
       maxMerge(amount_max)      AS amount_max,
       sumIfMerge(decline_count) AS declines,
       sumMerge(fraud_count)     AS frauds,
       uniqMerge(uniq_cards)     AS uniq_cards,
       uniqMerge(uniq_devices)   AS uniq_devices,
       sumMerge(intl_count)      AS intl_txns,
       declines / txns           AS decline_ratio,
       uniq_cards / uniq_devices AS cards_per_device   -- card-testing signal
FROM payments.agg_fraud_features
GROUP BY merchant_id, event_hour;
