-- ============================================================
-- settlement_summary — per merchant per cycle-date settlement performance
-- (volume, net, fees, failed count, average turnaround). Backs the Settlement
-- dashboard's TAT / failure / volume KPIs.
-- ============================================================
CREATE TABLE IF NOT EXISTS payments.agg_settlement
(
    merchant_id   LowCardinality(String),
    cycle_date    Date,
    batch_count   AggregateFunction(count),
    txn_count     AggregateFunction(sum, UInt32),
    gross_amount  AggregateFunction(sum, Decimal(18, 2)),
    net_amount    AggregateFunction(sum, Decimal(18, 2)),
    mdr_amount    AggregateFunction(sum, Decimal(18, 4)),
    paid_count    AggregateFunction(sumIf, UInt8, UInt8),
    failed_count  AggregateFunction(sumIf, UInt8, UInt8),
    avg_tat_mins  AggregateFunction(avg, UInt32)
)
ENGINE = AggregatingMergeTree
PARTITION BY toYYYYMM(cycle_date)
ORDER BY (merchant_id, cycle_date);

CREATE MATERIALIZED VIEW IF NOT EXISTS payments.mv_settlement
TO payments.agg_settlement AS
SELECT merchant_id,
       cycle_date,
       countState()                              AS batch_count,
       sumState(txn_count)                       AS txn_count,
       sumState(gross_amount)                    AS gross_amount,
       sumState(net_amount)                      AS net_amount,
       sumState(mdr_amount)                       AS mdr_amount,
       sumIfState(toUInt8(1), status = 'paid')   AS paid_count,
       sumIfState(toUInt8(1), status = 'failed') AS failed_count,
       avgState(tat_minutes)                     AS avg_tat_mins
FROM payments.fact_settlements
GROUP BY merchant_id, cycle_date;

CREATE VIEW IF NOT EXISTS payments.settlement_summary AS
SELECT merchant_id,
       cycle_date,
       countMerge(batch_count)  AS batches,
       sumMerge(txn_count)      AS txns,
       sumMerge(gross_amount)   AS gross_amount,
       sumMerge(net_amount)     AS net_settled,
       sumMerge(mdr_amount)     AS fees,
       sumIfMerge(paid_count)   AS paid_batches,
       sumIfMerge(failed_count) AS failed_batches,
       avgMerge(avg_tat_mins)   AS avg_tat_minutes
FROM payments.agg_settlement
GROUP BY merchant_id, cycle_date;
