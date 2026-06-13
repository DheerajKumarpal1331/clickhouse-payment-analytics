-- ============================================================
-- Module 3 — Customer: secondary indexes
-- ============================================================

-- Customer lookup by hashed phone (the primary identity key at support).
CREATE INDEX IF NOT EXISTS idx_customer_phone ON customer.customer_master (phone_hash);

-- Device-fingerprint reuse detection (fraud: one fingerprint, many customers).
CREATE INDEX IF NOT EXISTS idx_customer_device_fp
    ON customer.customer_devices (device_fingerprint);

-- Blacklist / high-risk filtering.
CREATE INDEX IF NOT EXISTS idx_customer_risk
    ON customer.customer_risk_profiles (risk_profile) WHERE is_blacklisted;
