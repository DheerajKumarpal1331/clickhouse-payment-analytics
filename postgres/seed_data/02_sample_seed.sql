-- ============================================================
-- Sample seed — a small but COMPLETE working dataset.
-- Drives the real stored procedures (sp_onboard_merchant,
-- sp_capture_transaction, sp_process_refund, sp_build_settlement_batch)
-- so loading it proves the whole OLTP lifecycle, triggers included.
--
-- Pure SQL (no external driver). Counts are constants at the top of
-- the DO block — bump them for a bigger sample, or use seed.py for
-- faker-style data at larger volume.
--
-- Idempotency: this seed assumes an empty transactional dataset.
-- Re-run on a fresh DB (apply.sh recreates), or TRUNCATE first.
-- ============================================================

DO $$
DECLARE
    n_merchants  INT := 200;
    n_customers  INT := 2000;
    n_txns       INT := 5000;

    mccs         TEXT[] := ARRAY['5411','5812','5912','5541','5999','5732','8062','5969','4111','8220'];
    methods      ref.payment_method[] := ARRAY['upi','upi','upi','debit_card','credit_card','wallet','qr','emi']::ref.payment_method[];
    cities       TEXT[];
    states       TEXT[];

    v_mid BIGINT; v_did BIGINT; v_cid BIGINT; v_txn BIGINT; v_refund BIGINT;
    dev_arr BIGINT[]; mer_arr BIGINT[]; mcc_arr TEXT[]; cust_arr BIGINT[];
    n_dev INT; k INT; i INT;
    v_method ref.payment_method; v_amount NUMERIC(18,2); v_loc BIGINT;
    v_bin CHAR(6); v_created TIMESTAMPTZ; v_ndev INT;
BEGIN
    SELECT array_agg(city ORDER BY location_id), array_agg(state ORDER BY location_id)
      INTO cities, states FROM ref.location;

    -- ---------------- Merchants (+ satellites via sp) ----------------
    FOR i IN 1..n_merchants LOOP
        v_loc := 1 + floor(random()*array_length(cities,1))::int;
        v_mid := merchant.sp_onboard_merchant(
            'M' || lpad(i::text, 7, '0'),
            'Seed Merchant ' || i || ' Pvt Ltd',
            (cities[v_loc] || ' ' || (mccs[1 + (i % 10)])::text || ' Store'),
            mccs[1 + floor(random()*10)::int]::char(4),
            md5('pan-' || i),
            (ARRAY['standard','enterprise','promo'])[1 + floor(random()*3)::int]
        );
        -- activate (fires status-history + audit triggers)
        UPDATE merchant.merchant_master SET status = 'active', activation_date = CURRENT_DATE
         WHERE id = v_mid;
        -- KYC verified
        UPDATE merchant.merchant_kyc SET kyc_status = 'verified', verified_at = now()
         WHERE merchant_id = v_mid;
        -- address + primary bank account
        INSERT INTO merchant.merchant_addresses (merchant_id, address_type, line1, location_id, is_primary)
        VALUES (v_mid, 'registered', i || ' Main Road', v_loc, TRUE);
        INSERT INTO merchant.merchant_bank_accounts (merchant_id, account_hash, ifsc, bank_code, is_primary, penny_drop_verified)
        VALUES (v_mid, md5('acct-' || i), 'HDFC0' || lpad((100000 + i)::text,6,'0'), 'HDFC', TRUE, TRUE);

        -- 1-3 devices per merchant
        v_ndev := 1 + floor(random()*3)::int;
        FOR k IN 1..v_ndev LOOP
            INSERT INTO device.device_master (device_code, serial_number, terminal_id, terminal_type, manufacturer, model)
            VALUES ('D' || lpad(((i*10)+k)::text, 8, '0'),
                    'SN' || lpad(((i*10)+k)::text, 10, '0'),
                    lpad(((i*10)+k)::text, 8, '0'),
                    (ARRAY['android_smartpos','linux_pos','mpos_dongle','soundbox_qr'])[1+floor(random()*4)::int],
                    'pax', 'A920')
            RETURNING id INTO v_did;
            INSERT INTO device.device_inventory (device_id, warehouse, stock_status) VALUES (v_did,'WH-MUM','deployed');
            INSERT INTO device.device_activation (device_id, activated_by) VALUES (v_did,'seed');
            INSERT INTO device.device_assignment (device_id, merchant_id) VALUES (v_did, v_mid);
            INSERT INTO device.device_firmware (device_id, firmware_version, app_version, is_current)
            VALUES (v_did, '3.1.0', '4.4.2', TRUE);
            INSERT INTO device.device_health (device_id, battery_level, last_heartbeat, health_score)
            VALUES (v_did, 50 + floor(random()*50)::int, now(), 0.9 + random()*0.1);
        END LOOP;
    END LOOP;

    -- ---------------- Customers ----------------
    FOR i IN 1..n_customers LOOP
        v_loc := 1 + floor(random()*array_length(cities,1))::int;
        INSERT INTO customer.customer_master (customer_code, age_band, gender, phone_hash, home_location_id, kyc_level)
        VALUES ('C' || lpad(i::text, 8, '0'),
                (ARRAY['18-25','26-35','36-45','46-60','60+'])[1+floor(random()*5)::int],
                (ARRAY['M','F','O'])[1+floor(random()*3)::int],
                md5('phone-' || i), v_loc,
                (ARRAY['min','full'])[1+floor(random()*2)::int])
        RETURNING id INTO v_cid;
        INSERT INTO customer.customer_risk_profiles (customer_id, risk_profile)
        VALUES (v_cid, (ARRAY['low','low','low','medium','high'])[1+floor(random()*5)::int]::ref.risk_tier);
        INSERT INTO customer.customer_payment_preferences (customer_id, preferred_method)
        VALUES (v_cid, (ARRAY['upi','debit_card','wallet'])[1+floor(random()*3)::int]::ref.payment_method);
    END LOOP;

    -- ---------------- Build pick-arrays ----------------
    SELECT array_agg(a.device_id), array_agg(a.merchant_id), array_agg(m.mcc)
      INTO dev_arr, mer_arr, mcc_arr
      FROM device.device_assignment a
      JOIN merchant.merchant_master m ON m.id = a.merchant_id
     WHERE a.released_at IS NULL;
    SELECT array_agg(id) INTO cust_arr FROM customer.customer_master;
    n_dev := array_length(dev_arr, 1);

    -- ---------------- Transactions (full lifecycle) ----------------
    FOR i IN 1..n_txns LOOP
        k := 1 + floor(random()*n_dev)::int;
        v_method := methods[1 + floor(random()*array_length(methods,1))::int];
        v_amount := round((10 + random()*5000)::numeric, 2);
        v_created := now() - (random()*7 || ' days')::interval;

        INSERT INTO txn.transaction_header
            (merchant_id, device_id, customer_id, rrn, stan, order_id, payment_method,
             channel, mcc, amount, state, response_code, fraud_label, created_at)
        VALUES (mer_arr[k], dev_arr[k], cust_arr[1+floor(random()*array_length(cust_arr,1))::int],
                lpad((floor(random()*1e12))::bigint::text,12,'0'), (floor(random()*1e6))::int,
                'ORD' || i, v_method, 'pos', mcc_arr[k]::char(4), v_amount, 'initiated', NULL,
                (random() < 0.004), v_created)
        RETURNING id INTO v_txn;

        INSERT INTO txn.transaction_details (transaction_id, base_amount) VALUES (v_txn, v_amount);
        INSERT INTO txn.payment_instruments (transaction_id, instrument_type, card_bin, card_network)
        VALUES (v_txn, v_method,
                CASE WHEN v_method IN ('credit_card','debit_card','emi')
                     THEN (ARRAY['421323','400123','521478','607432'])[1+floor(random()*4)::int] END,
                CASE WHEN v_method IN ('credit_card','debit_card','emi')
                     THEN (ARRAY['visa','mastercard','rupay'])[1+floor(random()*3)::int] END);

        -- ~92% succeed -> authorize + capture (sp computes fees); else fail
        IF random() < 0.92 THEN
            INSERT INTO txn.authorization_records (transaction_id, auth_code, auth_amount, issuer_bank, auth_latency_ms)
            VALUES (v_txn, lpad((floor(random()*1e6))::int::text,6,'0'), v_amount, 'HDFC', 100+floor(random()*400)::int);
            PERFORM txn.sp_capture_transaction(v_txn);

            -- ~1.5% of captured get refunded
            IF random() < 0.015 THEN
                INSERT INTO refund.refund_requests
                    (refund_code, transaction_id, merchant_id, requested_amount, original_amount, reason)
                VALUES ('RF' || v_txn, v_txn, mer_arr[k], v_amount, v_amount, 'customer_request')
                RETURNING id INTO v_refund;
                PERFORM refund.sp_process_refund(v_refund, 'seed');
            END IF;
        ELSE
            INSERT INTO txn.payment_attempts (transaction_id, response_code, response_message, latency_ms)
            VALUES (v_txn, '05', 'DO NOT HONOR', 100+floor(random()*400)::int);
            UPDATE txn.transaction_header
               SET state = 'failed', is_success = FALSE, response_code = '05' WHERE id = v_txn;
        END IF;
    END LOOP;

    -- ---------------- Settlement batches (last 3 days) ----------------
    FOR i IN 1..3 LOOP
        PERFORM settlement.sp_build_settlement_batch((CURRENT_DATE - i));
    END LOOP;

    -- ---------------- A few chargebacks + fraud scores + tickets ----------------
    INSERT INTO chargeback.chargeback_cases (case_code, transaction_id, merchant_id, network, reason_code, reason_category, respond_by)
    SELECT 'CB' || th.id, th.id, th.merchant_id, 'visa', '10.4', 'fraud', CURRENT_DATE + 7
      FROM txn.transaction_header th WHERE th.state = 'captured' ORDER BY random() LIMIT 20;
    INSERT INTO chargeback.chargeback_financials (case_id, dispute_amount, liability)
    SELECT c.id, th.amount, 'merchant'
      FROM chargeback.chargeback_cases c JOIN txn.transaction_header th ON th.id = c.transaction_id;

    INSERT INTO fraud.fraud_scores (transaction_id, merchant_id, model_version, score, risk_level)
    SELECT th.id, th.merchant_id, 'xgb_v1',
           round((random())::numeric,5),
           (ARRAY['low','low','medium','high','critical'])[1+floor(random()*5)::int]::ref.risk_tier
      FROM txn.transaction_header th ORDER BY random() LIMIT 500;

    INSERT INTO support.support_tickets (ticket_code, merchant_id, category, priority, subject, status)
    SELECT 'TKT' || m.id, m.id,
           (ARRAY['settlement','device','txn_dispute','kyc'])[1+floor(random()*4)::int],
           (ARRAY['low','medium','high','urgent'])[1+floor(random()*4)::int],
           'Seed ticket', 'open'
      FROM merchant.merchant_master m ORDER BY random() LIMIT 50;
    INSERT INTO support.sla_tracking (ticket_id, sla_target_mins, resolution_due_at)
    SELECT id, 240, now() + interval '4 hours' FROM support.support_tickets;

    RAISE NOTICE 'Seed complete: % merchants, % customers, % transactions', n_merchants, n_customers, n_txns;
END $$;
