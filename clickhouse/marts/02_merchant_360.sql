-- ============================================================
-- Merchant 360 — one row per merchant joining the dimension with last-30-day
-- activity and risk. Backs the Merchant Insights dashboard's merchant detail.
-- ============================================================
CREATE VIEW IF NOT EXISTS payments.mart_merchant_360 AS
SELECT m.merchant_id,
       m.dba_name,
       m.business_type,
       m.mcc,
       m.city,
       m.state,
       m.risk_tier,
       m.settlement_cycle,
       m.onboarded_date,
       m.status,
       a.txns_30d,
       a.gross_30d,
       a.revenue_30d,
       a.success_rate_30d,
       a.frauds_30d,
       a.active_customers_30d
FROM payments.dim_merchants AS m FINAL
LEFT JOIN
(
    SELECT merchant_id,
           sum(txns)                  AS txns_30d,
           sum(gross_amount)          AS gross_30d,
           sum(revenue)               AS revenue_30d,
           sum(successes) / sum(txns) AS success_rate_30d,
           sum(frauds)                AS frauds_30d,
           max(uniq_customers)        AS active_customers_30d
    FROM payments.merchant_daily_summary
    WHERE event_date >= today() - 30
    GROUP BY merchant_id
) AS a ON a.merchant_id = m.merchant_id;
