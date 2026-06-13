-- ============================================================
-- Executive mart — platform-wide daily KPIs for the Executive dashboard:
-- TPV, revenue (MDR), transactions, success rate, active merchants, fraud.
-- Reads the daily rollup (not raw facts) so it stays fast at scale.
-- ============================================================
CREATE VIEW IF NOT EXISTS payments.mart_executive_kpis AS
SELECT event_date,
       sum(txns)                AS transactions,
       sum(gross_amount)        AS tpv,                 -- total payment volume
       sum(revenue)             AS revenue,             -- MDR earned
       sum(successes) / sum(txns) AS success_rate,
       uniqExact(merchant_id)   AS active_merchants,
       sum(uniq_customers)      AS customer_touchpoints,
       sum(frauds)              AS fraud_txns
FROM payments.merchant_daily_summary
GROUP BY event_date
ORDER BY event_date;

-- Payment-method mix (Executive funnel / breakdown).
CREATE VIEW IF NOT EXISTS payments.mart_method_mix AS
SELECT toDate(event_time)         AS event_date,
       payment_method,
       count()                    AS txns,
       sum(amount)                AS volume,
       sum(is_success) / count()  AS success_rate
FROM payments.fact_transactions
GROUP BY event_date, payment_method
ORDER BY event_date, volume DESC;
