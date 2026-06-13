-- ============================================================
-- Fraud mart — daily fraud trend, loss, and decline pressure for the Risk &
-- Fraud dashboard. Fraud loss (sum of fraud-txn amounts) needs the fact, so
-- this view scans fact_transactions; materialize it if it gets hot.
-- ============================================================
CREATE VIEW IF NOT EXISTS payments.mart_fraud_daily AS
SELECT toDate(event_time)              AS event_date,
       count()                         AS txns,
       sum(fraud_label)                AS fraud_txns,
       sum(fraud_label) / count()      AS fraud_rate,
       sumIf(amount, fraud_label = 1)  AS fraud_loss,
       countIf(is_success = 0)         AS declines,
       countIf(is_success = 0) / count() AS decline_rate,
       uniqExactIf(card_hash, fraud_label = 1) AS distinct_fraud_cards
FROM payments.fact_transactions
GROUP BY event_date
ORDER BY event_date;

-- Fraud-scenario breakdown (what kinds of attacks, and their cost).
CREATE VIEW IF NOT EXISTS payments.mart_fraud_by_scenario AS
SELECT fraud_scenario,
       count()      AS txns,
       sum(amount)  AS amount,
       uniqExact(merchant_id) AS merchants_hit
FROM payments.fact_transactions
WHERE fraud_label = 1 AND fraud_scenario != ''
GROUP BY fraud_scenario
ORDER BY txns DESC;

-- Model scoring outcomes from the fraud API (joins risk bands).
CREATE VIEW IF NOT EXISTS payments.mart_fraud_scores AS
SELECT toDate(scored_at) AS event_date,
       risk_level,
       count()      AS scored,
       avg(score)   AS avg_score,
       avg(latency_ms) AS avg_latency_ms
FROM payments.fact_fraud_events
GROUP BY event_date, risk_level
ORDER BY event_date, risk_level;
