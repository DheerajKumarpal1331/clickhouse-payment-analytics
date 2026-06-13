-- ============================================================
-- Module 2 — Device: secondary indexes
-- ============================================================

-- "Which devices does this merchant have?" (assignment screen, ops).
CREATE INDEX IF NOT EXISTS idx_device_assign_merchant ON device.device_assignment (merchant_id);

-- Fleet health monitoring: find stale heartbeats / offline terminals.
CREATE INDEX IF NOT EXISTS idx_device_health_heartbeat ON device.device_health (last_heartbeat);
CREATE INDEX IF NOT EXISTS idx_device_health_fk        ON device.device_health (device_id, observed_at DESC);

-- Current firmware lookup per device (TMS / OTA rollout tracking).
CREATE INDEX IF NOT EXISTS idx_device_firmware_current
    ON device.device_firmware (device_id) WHERE is_current;

-- Network status timeline per device.
CREATE INDEX IF NOT EXISTS idx_device_network_fk ON device.device_network_status (device_id, observed_at DESC);
