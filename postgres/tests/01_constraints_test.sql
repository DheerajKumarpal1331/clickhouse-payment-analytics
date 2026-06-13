-- ============================================================
-- TEST 01 — Constraints enforce business rules.
-- Each block expects a specific error; if the bad write SUCCEEDS,
-- we RAISE EXCEPTION to fail the test. Uses savepoints so a caught
-- error doesn't abort the rest of the file.
-- ============================================================
\set ON_ERROR_STOP on

DO $$
BEGIN
    RAISE NOTICE '--- 01 constraints ---';

    -- (a) CHECK: transaction amount must be > 0
    BEGIN
        INSERT INTO txn.transaction_header (merchant_id, rrn, stan, payment_method, mcc, amount)
        SELECT id, '000000000001', 1, 'upi', mcc, -5 FROM merchant.merchant_master LIMIT 1;
        RAISE EXCEPTION 'FAIL: negative amount was accepted';
    EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: negative amount rejected (check_violation)';
    END;

    -- (b) FK: cannot reference a non-existent MCC
    BEGIN
        INSERT INTO merchant.merchant_master (merchant_code, legal_name, dba_name, mcc)
        VALUES ('M_BAD_MCC', 'x', 'x', '9999');
        RAISE EXCEPTION 'FAIL: invalid mcc FK was accepted';
    EXCEPTION WHEN foreign_key_violation THEN RAISE NOTICE 'PASS: invalid mcc FK rejected';
    END;

    -- (c) UNIQUE: merchant_code is unique
    BEGIN
        INSERT INTO merchant.merchant_master (merchant_code, legal_name, dba_name, mcc)
        VALUES ('M0000001', 'dup', 'dup', '5411');  -- M0000001 exists from seed
        RAISE EXCEPTION 'FAIL: duplicate merchant_code was accepted';
    EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'PASS: duplicate merchant_code rejected';
    END;

    -- (d) EXCLUDE: overlapping pricing windows forbidden
    BEGIN
        INSERT INTO merchant.merchant_pricing (merchant_id, effective_from, effective_to)
        SELECT merchant_id, CURRENT_DATE - 10, NULL FROM merchant.merchant_pricing LIMIT 1;
        RAISE EXCEPTION 'FAIL: overlapping pricing window was accepted';
    EXCEPTION WHEN exclusion_violation THEN RAISE NOTICE 'PASS: overlapping pricing window rejected';
    END;

    -- (e) partial UNIQUE: only one live device assignment per device
    BEGIN
        INSERT INTO device.device_assignment (device_id, merchant_id)
        SELECT a.device_id, a.merchant_id FROM device.device_assignment a
         WHERE a.released_at IS NULL LIMIT 1;
        RAISE EXCEPTION 'FAIL: second live device assignment was accepted';
    EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'PASS: duplicate live device assignment rejected';
    END;

    RAISE NOTICE '01 constraints: ALL PASS';
END $$;
