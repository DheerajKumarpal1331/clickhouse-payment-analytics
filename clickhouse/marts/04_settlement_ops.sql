-- ============================================================
-- Settlement + Operations marts.
-- ============================================================

-- Settlement dashboard: daily settled volume, TAT, failures.
CREATE VIEW IF NOT EXISTS payments.mart_settlement_daily AS
SELECT cycle_date,
       sum(txns)              AS txns,
       sum(gross_amount)      AS gross_amount,
       sum(net_settled)       AS net_settled,
       sum(fees)              AS fees,
       sum(failed_batches)    AS failed_batches,
       avg(avg_tat_minutes)   AS avg_tat_minutes,
       uniqExact(merchant_id) AS merchants_settled
FROM payments.settlement_summary
GROUP BY cycle_date
ORDER BY cycle_date;

-- Operations: hourly approval rate by method (issuer/rail health).
CREATE VIEW IF NOT EXISTS payments.mart_ops_approval AS
SELECT toStartOfHour(event_time)   AS event_hour,
       payment_method,
       count()                     AS txns,
       sum(is_success) / count()   AS approval_rate,
       avg(auth_latency_ms)        AS avg_auth_latency_ms
FROM payments.fact_transactions
GROUP BY event_hour, payment_method
ORDER BY event_hour DESC, txns DESC;

-- Operations: decline-reason distribution (RC code taxonomy).
CREATE VIEW IF NOT EXISTS payments.mart_ops_declines AS
SELECT response_code,
       response_message,
       count() AS declines
FROM payments.fact_transactions
WHERE is_success = 0
GROUP BY response_code, response_message
ORDER BY declines DESC;
