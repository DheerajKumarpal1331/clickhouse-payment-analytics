-- ============================================================
-- Module 1 — Merchant: secondary (performance) indexes
-- Correctness constraints (PK/UNIQUE/EXCLUDE/partial-unique) stay
-- with the tables in ddl/. These are query-acceleration only.
-- ============================================================

-- Portfolio filters: "active merchants", segment breakdowns.
CREATE INDEX IF NOT EXISTS idx_merchant_status ON merchant.merchant_master (status);
CREATE INDEX IF NOT EXISTS idx_merchant_mcc    ON merchant.merchant_master (mcc);

-- Fuzzy merchant search by trade name (support / ops console).
CREATE INDEX IF NOT EXISTS idx_merchant_name_trgm
    ON merchant.merchant_master USING gin (dba_name gin_trgm_ops);

-- Satellite lookups by merchant (onboarding & profile screens).
CREATE INDEX IF NOT EXISTS idx_merchant_bank_fk ON merchant.merchant_bank_accounts (merchant_id);
CREATE INDEX IF NOT EXISTS idx_merchant_docs_fk ON merchant.merchant_documents (merchant_id);
CREATE INDEX IF NOT EXISTS idx_merchant_status_hist_fk
    ON merchant.merchant_status_history (merchant_id, changed_at DESC);

-- Audit log queried by (table, row) when investigating a change.
CREATE INDEX IF NOT EXISTS idx_merchant_audit_row
    ON merchant.merchant_audit_log (table_name, row_pk, changed_at DESC);
