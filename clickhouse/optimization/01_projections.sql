-- ============================================================
-- Projections — alternate physical orderings/aggregates ClickHouse maintains
-- inside the same table, picked automatically when a query matches. They give
-- a second access path without a second table to keep in sync.
-- (ADD is idempotent; MATERIALIZE backfills existing parts.)
-- ============================================================

-- Aggregate projection: payment-method × day rollup. Turns the Executive
-- method-mix / approval queries into a tiny pre-aggregated read.
ALTER TABLE payments.fact_transactions
    ADD PROJECTION IF NOT EXISTS proj_method_daily
    (
        SELECT
            payment_method,
            toDate(event_time) AS d,
            count(),
            sum(amount),
            sum(is_success)
        GROUP BY payment_method, d
    );
ALTER TABLE payments.fact_transactions MATERIALIZE PROJECTION proj_method_daily;

-- Aggregate projection: card-network × day (network performance / interchange).
ALTER TABLE payments.fact_transactions
    ADD PROJECTION IF NOT EXISTS proj_network_daily
    (
        SELECT
            card_network,
            toDate(event_time) AS d,
            count(),
            sum(amount),
            sum(mdr_amount)
        GROUP BY card_network, d
    );
ALTER TABLE payments.fact_transactions MATERIALIZE PROJECTION proj_network_daily;

-- NOTE (documented, not enabled by default): a sorted projection
--   ADD PROJECTION proj_by_customer (SELECT * ORDER BY customer_id)
-- accelerates customer-history point lookups but ~doubles storage on this wide
-- table. The bloom_filter skip index on customer_id already covers the common
-- case; enable the projection only if customer-360 scans become hot.
