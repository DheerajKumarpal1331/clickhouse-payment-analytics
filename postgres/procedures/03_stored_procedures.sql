-- ============================================================
-- Stored procedures — business operations.
-- These encapsulate the multi-table writes each lifecycle needs,
-- so application code (and the seeder) calls one function instead
-- of orchestrating inserts and risking a half-written state.
-- ============================================================

-- ---------- Merchant onboarding (atomic 5-table insert) ----------
CREATE OR REPLACE FUNCTION merchant.sp_onboard_merchant(
    p_code TEXT, p_legal TEXT, p_dba TEXT, p_mcc CHAR(4),
    p_pan_hash TEXT, p_plan TEXT DEFAULT 'standard'
) RETURNS BIGINT AS $$
DECLARE v_id BIGINT;
BEGIN
    INSERT INTO merchant.merchant_master (merchant_code, legal_name, dba_name, mcc, status)
    VALUES (p_code, p_legal, p_dba, p_mcc, 'pending')
    RETURNING id INTO v_id;

    INSERT INTO merchant.merchant_kyc (merchant_id, pan_hash, kyc_status)
    VALUES (v_id, p_pan_hash, 'pending');

    INSERT INTO merchant.merchant_risk_profiles (merchant_id) VALUES (v_id);
    INSERT INTO merchant.merchant_pricing (merchant_id, pricing_plan) VALUES (v_id, p_plan);
    INSERT INTO merchant.merchant_settlement_configuration (merchant_id) VALUES (v_id);
    RETURN v_id;
END $$ LANGUAGE plpgsql;

-- ---------- Fee computation (MDR + interchange + GST + net) ----------
CREATE OR REPLACE FUNCTION txn.sp_compute_fees(p_txn_id BIGINT) RETURNS NUMERIC AS $$
DECLARE
    v_amt NUMERIC(18,2); v_method ref.payment_method; v_merchant BIGINT;
    v_bps SMALLINT; v_mdr NUMERIC(18,4); v_gst NUMERIC(18,4); v_net NUMERIC(18,2);
BEGIN
    SELECT amount, payment_method, merchant_id
      INTO v_amt, v_method, v_merchant
      FROM txn.transaction_header WHERE id = p_txn_id;

    SELECT CASE v_method
              WHEN 'credit_card' THEN mdr_card_credit_bps
              WHEN 'debit_card'  THEN mdr_card_debit_bps
              WHEN 'upi'         THEN mdr_upi_bps
              WHEN 'wallet'      THEN mdr_wallet_bps
              WHEN 'emi'         THEN mdr_emi_bps
              ELSE 90 END
      INTO v_bps
      FROM merchant.merchant_pricing
     WHERE merchant_id = v_merchant
       AND effective_to IS NULL
     ORDER BY effective_from DESC LIMIT 1;

    v_bps := COALESCE(v_bps, 90);
    v_mdr := round(v_amt * v_bps / 10000.0, 4);
    v_gst := round(v_mdr * 0.18, 4);
    v_net := round(v_amt - v_mdr - v_gst, 2);

    INSERT INTO txn.transaction_fees
        (transaction_id, mdr_rate_bps, mdr_amount, interchange_fee, network_fee, net_settlement_amount)
    VALUES (p_txn_id, v_bps, v_mdr, round(v_mdr*0.7,4), round(v_mdr*0.1,4), v_net);
    INSERT INTO txn.transaction_taxes (transaction_id, gst_on_fees) VALUES (p_txn_id, v_gst);
    RETURN v_net;
END $$ LANGUAGE plpgsql;

-- ---------- Capture a transaction (state -> captured, fees) ----------
CREATE OR REPLACE FUNCTION txn.sp_capture_transaction(p_txn_id BIGINT) RETURNS NUMERIC AS $$
DECLARE v_amt NUMERIC(18,2);
BEGIN
    UPDATE txn.transaction_header
       SET state = 'captured', is_success = TRUE
     WHERE id = p_txn_id AND state IN ('initiated','authorized')
    RETURNING amount INTO v_amt;

    IF v_amt IS NULL THEN
        RAISE EXCEPTION 'transaction % not in a capturable state', p_txn_id;
    END IF;

    INSERT INTO txn.capture_records (transaction_id, capture_amount, capture_mode)
    VALUES (p_txn_id, v_amt, 'auto');

    RETURN txn.sp_compute_fees(p_txn_id);   -- returns net settlement amount
END $$ LANGUAGE plpgsql;

-- ---------- Process a refund (approve + book + history) ----------
CREATE OR REPLACE FUNCTION refund.sp_process_refund(
    p_refund_id BIGINT, p_approver TEXT DEFAULT 'system'
) RETURNS BIGINT AS $$
DECLARE v_amt NUMERIC(18,2); v_txn_id BIGINT; v_refund_txn_id BIGINT;
BEGIN
    SELECT requested_amount, transaction_id INTO v_amt, v_txn_id
      FROM refund.refund_requests WHERE id = p_refund_id;
    IF v_amt IS NULL THEN
        RAISE EXCEPTION 'refund % not found', p_refund_id;
    END IF;

    INSERT INTO refund.refund_approvals (refund_id, approver, decision)
    VALUES (p_refund_id, p_approver, 'approved');

    UPDATE refund.refund_requests SET status = 'processed' WHERE id = p_refund_id;
    INSERT INTO refund.refund_status_history (refund_id, from_status, to_status)
    VALUES (p_refund_id, 'requested', 'processed');

    UPDATE txn.transaction_header SET state = 'refunded' WHERE id = v_txn_id;

    INSERT INTO refund.refund_transactions
        (refund_id, arn, refund_amount, refund_type, processed_at, status)
    VALUES (p_refund_id,
            '74' || lpad((floor(random()*1e10))::bigint::text, 10, '0'),
            v_amt, 'online', now(), 'processed')
    RETURNING id INTO v_refund_txn_id;

    RETURN v_refund_txn_id;
END $$ LANGUAGE plpgsql;

-- ---------- Build a settlement batch for a cycle date ----------
-- Nets captured txns per merchant (gross - MDR - GST) into
-- merchant_settlements, then rolls the totals up onto the batch.
CREATE OR REPLACE FUNCTION settlement.sp_build_settlement_batch(p_cycle_date DATE)
RETURNS BIGINT AS $$
DECLARE
    v_batch_id BIGINT;
    v_code TEXT := 'BATCH-' || to_char(p_cycle_date, 'YYYYMMDD');
BEGIN
    INSERT INTO settlement.settlement_batches (batch_code, cycle_date, settlement_cycle, status)
    VALUES (v_code, p_cycle_date, 'T+1', 'pending')
    RETURNING id INTO v_batch_id;

    INSERT INTO settlement.merchant_settlements
        (batch_id, merchant_id, txn_count, gross_amount, mdr_amount, gst_amount, net_amount, status)
    SELECT
        v_batch_id,
        th.merchant_id,
        count(*)::int,
        COALESCE(sum(th.amount), 0),
        COALESCE(sum(tf.mdr_amount), 0),
        COALESCE(sum(tt.gst_on_fees), 0),
        COALESCE(sum(tf.net_settlement_amount), 0),
        'pending'
    FROM txn.transaction_header th
    LEFT JOIN txn.transaction_fees  tf ON tf.transaction_id = th.id
    LEFT JOIN txn.transaction_taxes tt ON tt.transaction_id = th.id
    WHERE th.is_success
      AND th.state IN ('captured','refunded','partially_refunded')
      AND th.created_at::date = p_cycle_date
    GROUP BY th.merchant_id;

    UPDATE settlement.settlement_batches b
       SET total_merchants = s.n, gross_amount = s.g, net_amount = s.net
      FROM (SELECT count(*) n, COALESCE(sum(gross_amount),0) g, COALESCE(sum(net_amount),0) net
              FROM settlement.merchant_settlements WHERE batch_id = v_batch_id) s
     WHERE b.id = v_batch_id;

    RETURN v_batch_id;
END $$ LANGUAGE plpgsql;
