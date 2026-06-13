-- ============================================================
-- TEST 04 — Referential integrity & data sanity on the seeded set.
-- These are aggregate invariants the seeded data must satisfy.
-- ============================================================
\set ON_ERROR_STOP on

DO $$
DECLARE
    v_orphan_fees INT; v_orphan_details INT; v_bad_net INT;
    v_settle_rows INT; v_txn_rows INT; v_captured INT; v_neg INT;
    v_dup_primary_bank INT;
BEGIN
    RAISE NOTICE '--- 04 integrity ---';

    -- (a) no fee row without a parent transaction
    SELECT count(*) INTO v_orphan_fees
      FROM txn.transaction_fees f
      LEFT JOIN txn.transaction_header h ON h.id = f.transaction_id
     WHERE h.id IS NULL;
    ASSERT v_orphan_fees = 0, format('FAIL: %s orphan fee rows', v_orphan_fees);
    RAISE NOTICE 'PASS: no orphan transaction_fees';

    -- (b) no detail row without a parent transaction
    SELECT count(*) INTO v_orphan_details
      FROM txn.transaction_details d
      LEFT JOIN txn.transaction_header h ON h.id = d.transaction_id
     WHERE h.id IS NULL;
    ASSERT v_orphan_details = 0, format('FAIL: %s orphan detail rows', v_orphan_details);
    RAISE NOTICE 'PASS: no orphan transaction_details';

    -- (c) net settlement never exceeds gross amount (fees are non-negative)
    SELECT count(*) INTO v_bad_net
      FROM txn.transaction_fees f JOIN txn.transaction_header h ON h.id = f.transaction_id
     WHERE f.net_settlement_amount > h.amount;
    ASSERT v_bad_net = 0, format('FAIL: %s txns with net > gross', v_bad_net);
    RAISE NOTICE 'PASS: net settlement <= gross for all txns';

    -- (d) captured transactions all have a fee row
    SELECT count(*) INTO v_captured FROM txn.transaction_header WHERE state IN ('captured','refunded','partially_refunded');
    SELECT count(*) INTO v_txn_rows
      FROM txn.transaction_header h
     WHERE h.state IN ('captured','refunded','partially_refunded')
       AND NOT EXISTS (SELECT 1 FROM txn.transaction_fees f WHERE f.transaction_id = h.id);
    ASSERT v_txn_rows = 0, format('FAIL: %s captured txns missing fees', v_txn_rows);
    RAISE NOTICE 'PASS: all % captured txns have fees', v_captured;

    -- (e) settlement batches were built and have merchant rows
    SELECT count(*) INTO v_settle_rows FROM settlement.merchant_settlements;
    ASSERT v_settle_rows > 0, 'FAIL: no merchant_settlements produced';
    RAISE NOTICE 'PASS: % merchant_settlements rows', v_settle_rows;

    -- (f) no negative amounts slipped in
    SELECT count(*) INTO v_neg FROM txn.transaction_header WHERE amount <= 0;
    ASSERT v_neg = 0, 'FAIL: non-positive amounts present';
    RAISE NOTICE 'PASS: all amounts positive';

    -- (g) at most one primary bank account per merchant
    SELECT count(*) INTO v_dup_primary_bank FROM (
        SELECT merchant_id FROM merchant.merchant_bank_accounts WHERE is_primary
        GROUP BY merchant_id HAVING count(*) > 1
    ) x;
    ASSERT v_dup_primary_bank = 0, 'FAIL: merchant with >1 primary bank account';
    RAISE NOTICE 'PASS: <=1 primary bank account per merchant';

    RAISE NOTICE '04 integrity: ALL PASS';
END $$;
