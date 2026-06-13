#!/usr/bin/env python3
"""Alternative seeder for larger / faker-style volumes.

The SQL seeder (02_sample_seed.sql) is the validated default and needs no
driver. This Python version is for when you want more rows or more realistic
entity attributes — it reuses the data-generator's entity builders and drives
the same stored procedures via psycopg2.

Usage
-----
    pip install psycopg2-binary
    python seed.py --dsn postgresql://postgres:postgres@localhost:5432/payments \
                   --merchants 1000 --customers 20000 --transactions 50000

Run AFTER ddl/ + indexes/ + procedures/ + 01_reference_data.sql are applied.
"""
from __future__ import annotations

import argparse
import hashlib
import random
import sys

MCCS = ['5411', '5812', '5912', '5541', '5999', '5732', '8062', '5969', '4111', '8220']
METHODS = ['upi', 'upi', 'upi', 'debit_card', 'credit_card', 'wallet', 'qr', 'emi']
TERMINALS = ['android_smartpos', 'linux_pos', 'mpos_dongle', 'soundbox_qr']
BINS = ['421323', '400123', '521478', '607432']


def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def main() -> int:
    try:
        import psycopg2
        from psycopg2.extras import execute_batch
    except ImportError:
        print("psycopg2 not installed — run: pip install psycopg2-binary", file=sys.stderr)
        return 1

    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="postgresql://postgres:postgres@localhost:5432/payments")
    ap.add_argument("--merchants", type=int, default=1000)
    ap.add_argument("--customers", type=int, default=20000)
    ap.add_argument("--transactions", type=int, default=50000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    conn = psycopg2.connect(args.dsn)
    conn.autocommit = False
    cur = conn.cursor()

    # ---- merchants via stored proc ----
    print(f"onboarding {args.merchants} merchants ...")
    merchant_ids = []
    for i in range(args.merchants):
        cur.execute(
            "SELECT merchant.sp_onboard_merchant(%s,%s,%s,%s,%s,%s)",
            (f"M{i:07d}", f"Seed Merchant {i} Pvt Ltd", f"Store {i}",
             rng.choice(MCCS), _h(f"pan-{i}"),
             rng.choice(['standard', 'enterprise', 'promo'])),
        )
        mid = cur.fetchone()[0]
        merchant_ids.append(mid)
        cur.execute("UPDATE merchant.merchant_master SET status='active' WHERE id=%s", (mid,))
        cur.execute(
            "INSERT INTO merchant.merchant_bank_accounts "
            "(merchant_id, account_hash, ifsc, bank_code, is_primary, penny_drop_verified) "
            "VALUES (%s,%s,%s,'HDFC',TRUE,TRUE)",
            (mid, _h(f"acct-{i}"), f"HDFC0{100000 + i:06d}"),
        )
    conn.commit()

    # ---- devices ----
    print("provisioning devices ...")
    device_rows = []  # (device_id, merchant_id)
    seq = 0
    for mid in merchant_ids:
        for _ in range(rng.randint(1, 3)):
            seq += 1
            cur.execute(
                "INSERT INTO device.device_master "
                "(device_code, serial_number, terminal_id, terminal_type, manufacturer, model) "
                "VALUES (%s,%s,%s,%s,'pax','A920') RETURNING id",
                (f"D{seq:08d}", f"SN{seq:010d}", f"{seq:08d}", rng.choice(TERMINALS)),
            )
            did = cur.fetchone()[0]
            cur.execute("INSERT INTO device.device_assignment (device_id, merchant_id) VALUES (%s,%s)", (did, mid))
            device_rows.append((did, mid))
    conn.commit()

    # ---- customers ----
    print(f"creating {args.customers} customers ...")
    customer_ids = []
    batch = []
    for i in range(args.customers):
        batch.append((f"C{i:08d}", rng.choice(['18-25', '26-35', '36-45', '46-60', '60+']),
                      rng.choice(['M', 'F', 'O']), _h(f"phone-{i}"), rng.choice(['min', 'full'])))
    execute_batch(cur,
                  "INSERT INTO customer.customer_master "
                  "(customer_code, age_band, gender, phone_hash, kyc_level) VALUES (%s,%s,%s,%s,%s)",
                  batch, page_size=1000)
    conn.commit()
    cur.execute("SELECT id FROM customer.customer_master")
    customer_ids = [r[0] for r in cur.fetchall()]

    # ---- transactions (full lifecycle via sp_capture) ----
    print(f"processing {args.transactions} transactions ...")
    mcc_by_merchant = {}
    cur.execute("SELECT id, mcc FROM merchant.merchant_master")
    for mid, mcc in cur.fetchall():
        mcc_by_merchant[mid] = mcc

    for i in range(args.transactions):
        did, mid = rng.choice(device_rows)
        cid = rng.choice(customer_ids)
        method = rng.choice(METHODS)
        amount = round(rng.uniform(10, 5000), 2)
        cur.execute(
            "INSERT INTO txn.transaction_header "
            "(merchant_id, device_id, customer_id, rrn, stan, order_id, payment_method, "
            " channel, mcc, amount, state, fraud_label, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,'pos',%s,%s,'initiated',%s, now() - (%s||' days')::interval) "
            "RETURNING id",
            (mid, did, cid, f"{rng.randrange(10**11, 10**12):012d}", rng.randrange(10**6),
             f"ORD{i}", method, mcc_by_merchant[mid], amount, rng.random() < 0.004,
             rng.uniform(0, 7)),
        )
        txn_id = cur.fetchone()[0]
        cur.execute("INSERT INTO txn.transaction_details (transaction_id, base_amount) VALUES (%s,%s)",
                    (txn_id, amount))
        if rng.random() < 0.92:
            cur.execute("INSERT INTO txn.authorization_records (transaction_id, auth_amount, issuer_bank) "
                        "VALUES (%s,%s,'HDFC')", (txn_id, amount))
            cur.execute("SELECT txn.sp_capture_transaction(%s)", (txn_id,))
        else:
            cur.execute("UPDATE txn.transaction_header SET state='failed', is_success=FALSE, response_code='05' "
                        "WHERE id=%s", (txn_id,))
        if i % 5000 == 0:
            conn.commit()
            print(f"  {i:,} txns")
    conn.commit()

    # ---- settlement batches ----
    for d in range(1, 4):
        cur.execute("SELECT settlement.sp_build_settlement_batch((CURRENT_DATE - %s))", (d,))
    conn.commit()

    cur.close()
    conn.close()
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
