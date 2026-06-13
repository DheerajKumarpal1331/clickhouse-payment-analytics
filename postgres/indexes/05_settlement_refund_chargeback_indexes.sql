-- ============================================================
-- Modules 5/6/7 — Settlement, Refund, Chargeback: secondary indexes
-- ============================================================

-- Settlement
CREATE INDEX IF NOT EXISTS idx_settle_merchant ON settlement.merchant_settlements (merchant_id);
CREATE INDEX IF NOT EXISTS idx_settle_batch    ON settlement.merchant_settlements (batch_id);
CREATE INDEX IF NOT EXISTS idx_settle_batch_cycle ON settlement.settlement_batches (cycle_date);
CREATE INDEX IF NOT EXISTS idx_bank_transfer_utr ON settlement.bank_transfers (utr);
CREATE INDEX IF NOT EXISTS idx_settle_exc_open
    ON settlement.settlement_exceptions (created_at) WHERE NOT resolved;

-- Refund
CREATE INDEX IF NOT EXISTS idx_refund_txn      ON refund.refund_requests (transaction_id);
CREATE INDEX IF NOT EXISTS idx_refund_merchant ON refund.refund_requests (merchant_id, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_refund_status   ON refund.refund_requests (status);

-- Chargeback
CREATE INDEX IF NOT EXISTS idx_cb_merchant ON chargeback.chargeback_cases (merchant_id, opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_cb_txn      ON chargeback.chargeback_cases (transaction_id);
-- Open cases approaching their respond-by deadline (the urgent work queue).
CREATE INDEX IF NOT EXISTS idx_cb_open_due
    ON chargeback.chargeback_cases (respond_by) WHERE status = 'open';
