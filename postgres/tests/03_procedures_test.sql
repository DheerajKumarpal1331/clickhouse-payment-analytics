-- ============================================================
-- TEST 03 — Stored procedures behave correctly.
-- ============================================================
\set ON_ERROR_STOP on

DO $$
DECLARE
    v_mid BIGINT; v_kyc INT; v_pricing INT; v_settle INT;
    v_txn BIGINT; v_net NUMERIC; v_mdr NUMERIC; v_gst NUMERIC; v_amount NUMERIC := 1000.00;
    v_refund BIGINT; v_refund_txn BIGINT; v_state ref.txn_state;
BEGIN
    RAISE NOTICE '--- 03 procedures ---';

    -- (a) sp_onboard_merchant creates all 5 rows atomically
    v_mid := merchant.sp_onboard_merchant('M_TEST_SP', 'Test SP Ltd', 'Test SP', '5411', md5('pan-test'), 'standard');
    SELECT count(*) INTO v_kyc     FROM merchant.merchant_kyc WHERE merchant_id = v_mid;
    SELECT count(*) INTO v_pricing FROM merchant.merchant_pricing WHERE merchant_id = v_mid;
    SELECT count(*) INTO v_settle  FROM merchant.merchant_settlement_configuration WHERE merchant_id = v_mid;
    ASSERT v_kyc = 1 AND v_pricing = 1 AND v_settle = 1, 'FAIL: onboarding did not create all satellites';
    RAISE NOTICE 'PASS: sp_onboard_merchant created master + kyc + pricing + risk + settlement';

    -- (b) sp_compute_fees via sp_capture_transaction: net = amount - MDR - GST
    --     credit_card MDR default = 180 bps -> MDR=18.00, GST=3.24, net=978.76
    INSERT INTO txn.transaction_header (merchant_id, rrn, stan, payment_method, mcc, amount, state)
    VALUES (v_mid, '000000000100', 100, 'credit_card', '5411', v_amount, 'authorized')
    RETURNING id INTO v_txn;
    v_net := txn.sp_capture_transaction(v_txn);

    SELECT mdr_amount, net_settlement_amount INTO v_mdr, v_net FROM txn.transaction_fees WHERE transaction_id = v_txn;
    SELECT gst_on_fees INTO v_gst FROM txn.transaction_taxes WHERE transaction_id = v_txn;
    SELECT state INTO v_state FROM txn.transaction_header WHERE id = v_txn;
    ASSERT v_mdr = 18.0000, format('FAIL: MDR expected 18.0000 got %s', v_mdr);
    ASSERT v_gst = 3.2400,  format('FAIL: GST expected 3.2400 got %s', v_gst);
    ASSERT v_net = 978.76,  format('FAIL: net expected 978.76 got %s', v_net);
    ASSERT v_state = 'captured', 'FAIL: txn not captured';
    RAISE NOTICE 'PASS: fees MDR=% GST=% net=% , state=captured', v_mdr, v_gst, v_net;

    -- (c) sp_process_refund books refund txn + flips header to refunded
    INSERT INTO refund.refund_requests (refund_code, transaction_id, merchant_id, requested_amount, original_amount, reason)
    VALUES ('RF_TEST', v_txn, v_mid, v_amount, v_amount, 'customer_request')
    RETURNING id INTO v_refund;
    v_refund_txn := refund.sp_process_refund(v_refund, 'test');
    SELECT state INTO v_state FROM txn.transaction_header WHERE id = v_txn;
    ASSERT v_refund_txn IS NOT NULL, 'FAIL: refund txn not created';
    ASSERT v_state = 'refunded', format('FAIL: header state expected refunded got %s', v_state);
    RAISE NOTICE 'PASS: sp_process_refund booked refund #% , header=refunded', v_refund_txn;

    -- (d) capturing an already-captured txn must error
    BEGIN
        PERFORM txn.sp_capture_transaction(v_txn);
        RAISE EXCEPTION 'FAIL: re-capture of non-capturable txn succeeded';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM LIKE 'FAIL:%' THEN RAISE; END IF;
        RAISE NOTICE 'PASS: re-capture correctly rejected';
    END;

    RAISE NOTICE '03 procedures: ALL PASS';
END $$;
