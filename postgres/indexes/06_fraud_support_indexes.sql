-- ============================================================
-- Modules 8/9 — Fraud, Support: secondary indexes
-- ============================================================

-- Fraud
CREATE INDEX IF NOT EXISTS idx_fraud_score_txn  ON fraud.fraud_scores (transaction_id);
CREATE INDEX IF NOT EXISTS idx_fraud_score_time ON fraud.fraud_scores (scored_at DESC);
-- Open-alert work queue (only a small slice of all alerts).
CREATE INDEX IF NOT EXISTS idx_fraud_alert_open
    ON fraud.fraud_alerts (raised_at DESC) WHERE status = 'open';
CREATE INDEX IF NOT EXISTS idx_fraud_case_status ON fraud.fraud_cases (status);

-- Support
-- Agent queue: open/high-priority tickets first.
CREATE INDEX IF NOT EXISTS idx_ticket_status   ON support.support_tickets (status, priority);
CREATE INDEX IF NOT EXISTS idx_ticket_merchant ON support.support_tickets (merchant_id);
CREATE INDEX IF NOT EXISTS idx_ticket_comments_fk ON support.ticket_comments (ticket_id);
-- SLA breach monitoring.
CREATE INDEX IF NOT EXISTS idx_sla_breached
    ON support.sla_tracking (resolution_due_at) WHERE NOT breached;
