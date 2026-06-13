-- ============================================================
-- Maintenance & health queries (run ad-hoc or from an Airflow monitoring DAG).
-- These are SELECTs/OPTIMIZE — safe to run anytime.
-- ============================================================

-- Part counts per partition (merge pressure — alerts fire >300, see Phase 0.5).
-- SELECT table, partition, count() parts, sum(rows) rows
-- FROM system.parts WHERE database='payments' AND active GROUP BY table, partition
-- ORDER BY parts DESC LIMIT 20;

-- Compression effectiveness per column on the wide fact (storage tuning).
-- SELECT name, formatReadableSize(data_compressed_bytes) comp,
--        formatReadableSize(data_uncompressed_bytes) uncomp,
--        round(data_uncompressed_bytes / data_compressed_bytes, 1) ratio
-- FROM system.columns WHERE database='payments' AND table='fact_transactions'
-- ORDER BY data_compressed_bytes DESC LIMIT 20;

-- Force-merge a day's partition after a big backfill (rarely needed; merges
-- happen automatically). Example for one day:
-- OPTIMIZE TABLE payments.fact_transactions PARTITION '20260613' FINAL;

-- Verify a materialized view is populating (row counts of agg targets).
-- SELECT 'agg_merchant_daily' t, count() FROM payments.agg_merchant_daily
-- UNION ALL SELECT 'agg_fraud_features', count() FROM payments.agg_fraud_features
-- UNION ALL SELECT 'agg_velocity_5m', count() FROM payments.agg_velocity_5m;

-- Mutations / merges in flight (should be small and draining).
-- SELECT * FROM system.merges WHERE database='payments';
-- SELECT * FROM system.mutations WHERE database='payments' AND NOT is_done;
