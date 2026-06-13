-- ============================================================
-- TTL & table settings. TTL windows are declared inline on each table
-- (fact_transactions 18mo, fraud 6mo, velocity 7d, hourly aggregates 3mo).
-- Here we tune *how* TTL and merges behave.
-- ============================================================

-- Drop whole expired parts instead of rewriting them — far cheaper TTL eviction
-- on time-partitioned facts.
ALTER TABLE payments.fact_transactions   MODIFY SETTING ttl_only_drop_parts = 1;
ALTER TABLE payments.fact_fraud_events    MODIFY SETTING ttl_only_drop_parts = 1;
ALTER TABLE payments.agg_velocity_5m      MODIFY SETTING ttl_only_drop_parts = 1;
ALTER TABLE payments.agg_merchant_hourly  MODIFY SETTING ttl_only_drop_parts = 1;

-- Recommended server / session settings for the streaming sink (set on the
-- client/consumer side; documented here as the canonical values):
--   async_insert = 1                 -- batch small JSONEachRow inserts server-side
--   wait_for_async_insert = 1        -- still durable (waits for flush)
--   async_insert_busy_timeout_ms = 1000
--   max_insert_threads = 4
-- The Kafka consumer already batches (BATCH_SIZE/BATCH_MS), so async_insert is
-- optional; enable it if many low-volume topics insert tiny batches.
