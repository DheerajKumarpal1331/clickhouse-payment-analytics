-- ============================================================
-- Module 4 — Payment Processing: secondary indexes
-- The dominant OLTP access paths. On a partitioned table these are
-- created on the parent and propagate to every monthly partition.
-- ============================================================

-- #1 access path: a merchant's recent transactions (dashboards, statements).
CREATE INDEX IF NOT EXISTS idx_txn_merchant_time
    ON txn.transaction_header (merchant_id, created_at DESC);

-- Customer history (support "show me my charges").
CREATE INDEX IF NOT EXISTS idx_txn_customer ON txn.transaction_header (customer_id);

-- Point lookup by retrieval reference number (disputes / recon).
CREATE INDEX IF NOT EXISTS idx_txn_rrn ON txn.transaction_header (rrn);

-- Partial indexes: only index the rows we actually scan for.
--   failed txns (ops triage)         — tiny vs full table
--   fraud-labelled txns (analysis)   — ~0.4% of rows
CREATE INDEX IF NOT EXISTS idx_txn_failed
    ON txn.transaction_header (state) WHERE NOT is_success;
CREATE INDEX IF NOT EXISTS idx_txn_fraud
    ON txn.transaction_header (created_at) WHERE fraud_label;

-- Child-table FK joins (header -> details/attempts/auth/capture/fees).
CREATE INDEX IF NOT EXISTS idx_txn_details_fk  ON txn.transaction_details (transaction_id);
CREATE INDEX IF NOT EXISTS idx_txn_attempts_fk ON txn.payment_attempts (transaction_id);
CREATE INDEX IF NOT EXISTS idx_txn_auth_fk     ON txn.authorization_records (transaction_id);
CREATE INDEX IF NOT EXISTS idx_txn_capture_fk  ON txn.capture_records (transaction_id);
CREATE INDEX IF NOT EXISTS idx_txn_fees_fk     ON txn.transaction_fees (transaction_id);
CREATE INDEX IF NOT EXISTS idx_txn_instr_fk    ON txn.payment_instruments (transaction_id);

-- UPI / card detail joins + BIN analytics.
CREATE INDEX IF NOT EXISTS idx_upi_txn_fk  ON txn.upi_transactions (transaction_id);
CREATE INDEX IF NOT EXISTS idx_card_txn_fk ON txn.card_transactions (transaction_id);
CREATE INDEX IF NOT EXISTS idx_card_bin    ON txn.card_transactions (card_bin);
