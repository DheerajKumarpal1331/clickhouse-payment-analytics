-- ============================================================
-- Trigger wiring. Depends on procedures/01_functions.sql.
-- DROP-then-CREATE so the file is re-runnable.
-- ============================================================

-- ---------- merchant ----------
DROP TRIGGER IF EXISTS trg_merchant_touch  ON merchant.merchant_master;
DROP TRIGGER IF EXISTS trg_merchant_status ON merchant.merchant_master;
DROP TRIGGER IF EXISTS trg_merchant_audit  ON merchant.merchant_master;
CREATE TRIGGER trg_merchant_touch BEFORE UPDATE ON merchant.merchant_master
    FOR EACH ROW EXECUTE FUNCTION ref.touch_updated_at();
CREATE TRIGGER trg_merchant_status AFTER UPDATE ON merchant.merchant_master
    FOR EACH ROW EXECUTE FUNCTION merchant.log_status_change();
CREATE TRIGGER trg_merchant_audit AFTER INSERT OR UPDATE OR DELETE ON merchant.merchant_master
    FOR EACH ROW EXECUTE FUNCTION ref.audit_row('merchant.merchant_audit_log');

DROP TRIGGER IF EXISTS trg_pricing_touch ON merchant.merchant_pricing;
CREATE TRIGGER trg_pricing_touch BEFORE UPDATE ON merchant.merchant_pricing
    FOR EACH ROW EXECUTE FUNCTION ref.touch_updated_at();

-- ---------- device ----------
DROP TRIGGER IF EXISTS trg_device_touch ON device.device_master;
DROP TRIGGER IF EXISTS trg_device_audit ON device.device_master;
CREATE TRIGGER trg_device_touch BEFORE UPDATE ON device.device_master
    FOR EACH ROW EXECUTE FUNCTION ref.touch_updated_at();
CREATE TRIGGER trg_device_audit AFTER INSERT OR UPDATE OR DELETE ON device.device_master
    FOR EACH ROW EXECUTE FUNCTION ref.audit_row('device.device_audit_log');

-- ---------- customer ----------
DROP TRIGGER IF EXISTS trg_customer_touch ON customer.customer_master;
CREATE TRIGGER trg_customer_touch BEFORE UPDATE ON customer.customer_master
    FOR EACH ROW EXECUTE FUNCTION ref.touch_updated_at();

-- ---------- transaction ----------
DROP TRIGGER IF EXISTS trg_txn_touch ON txn.transaction_header;
DROP TRIGGER IF EXISTS trg_txn_state ON txn.transaction_header;
CREATE TRIGGER trg_txn_touch BEFORE UPDATE ON txn.transaction_header
    FOR EACH ROW EXECUTE FUNCTION ref.touch_updated_at();
CREATE TRIGGER trg_txn_state AFTER UPDATE ON txn.transaction_header
    FOR EACH ROW EXECUTE FUNCTION txn.log_state_change();
