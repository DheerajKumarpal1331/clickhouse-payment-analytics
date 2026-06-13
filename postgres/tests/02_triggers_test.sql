-- ============================================================
-- TEST 02 — Triggers fire correctly.
-- audit log written, status history written, updated_at touched,
-- transaction state history written.
-- ============================================================
\set ON_ERROR_STOP on

DO $$
DECLARE
    v_mid BIGINT; v_before INT; v_after INT; v_old TIMESTAMPTZ; v_new TIMESTAMPTZ;
    v_hist INT; v_txn BIGINT;
BEGIN
    RAISE NOTICE '--- 02 triggers ---';

    SELECT id, updated_at INTO v_mid, v_old FROM merchant.merchant_master ORDER BY id LIMIT 1;

    -- (a) audit log grows on UPDATE
    SELECT count(*) INTO v_before FROM merchant.merchant_audit_log WHERE row_pk = v_mid;
    UPDATE merchant.merchant_master SET relationship_manager = 'RM999' WHERE id = v_mid;
    SELECT count(*) INTO v_after FROM merchant.merchant_audit_log WHERE row_pk = v_mid;
    ASSERT v_after > v_before, 'FAIL: audit log not written on update';
    RAISE NOTICE 'PASS: audit row written (% -> %)', v_before, v_after;

    -- (b) updated_at touched
    SELECT updated_at INTO v_new FROM merchant.merchant_master WHERE id = v_mid;
    ASSERT v_new > v_old, 'FAIL: updated_at not advanced';
    RAISE NOTICE 'PASS: updated_at touched';

    -- (c) status change recorded in history
    SELECT count(*) INTO v_before FROM merchant.merchant_status_history WHERE merchant_id = v_mid;
    UPDATE merchant.merchant_master SET status = 'suspended' WHERE id = v_mid;
    SELECT count(*) INTO v_after FROM merchant.merchant_status_history WHERE merchant_id = v_mid;
    ASSERT v_after = v_before + 1, 'FAIL: status history not written';
    RAISE NOTICE 'PASS: status history written';
    UPDATE merchant.merchant_master SET status = 'active' WHERE id = v_mid;  -- restore

    -- (d) transaction state history on capture path
    INSERT INTO txn.transaction_header (merchant_id, rrn, stan, payment_method, mcc, amount, state)
    SELECT id, '000000000099', 99, 'upi', mcc, 100, 'initiated' FROM merchant.merchant_master WHERE id = v_mid
    RETURNING id INTO v_txn;
    UPDATE txn.transaction_header SET state = 'authorized' WHERE id = v_txn;
    UPDATE txn.transaction_header SET state = 'captured', is_success = TRUE WHERE id = v_txn;
    SELECT count(*) INTO v_hist FROM txn.transaction_status_history WHERE transaction_id = v_txn;
    ASSERT v_hist >= 2, 'FAIL: transaction state history missing transitions';
    RAISE NOTICE 'PASS: txn state history recorded % transitions', v_hist;
    -- keep this captured row consistent (fees) so it doesn't trip the
    -- global "captured txns must have fees" invariant in test 04.
    PERFORM txn.sp_compute_fees(v_txn);

    RAISE NOTICE '02 triggers: ALL PASS';
END $$;
