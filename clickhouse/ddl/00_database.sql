-- ============================================================
-- ClickHouse Analytics Warehouse (Phase 5)
-- 00: database. Idempotent — also created by the Phase 0.5 init.
-- Apply order: ddl/ -> materialized_views/ -> features/ -> marts/ -> optimization/
-- (docker/clickhouse/apply.sh runs them in that order; the init mounts the
--  same files so the warehouse is auto-created on `docker compose up -d`.)
-- ============================================================
CREATE DATABASE IF NOT EXISTS payments;
