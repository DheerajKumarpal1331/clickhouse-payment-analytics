"""Continuous OLTP generator — streams fresh transactions into Postgres.

This is the *source* of the live pipeline: it INSERTs new rows into
`txn.transaction_header` at a steady rate, which the watermark-CDC producer
(kafka/producers) then picks up → Kafka → ClickHouse → dashboard. Run it and
the whole platform comes alive end-to-end (the dashboard's realtime strip,
Kafka lag, ClickHouse ingest, fraud scoring traffic).

It samples *existing* merchant / device / customer keys (so every row satisfies
the foreign keys) and writes realistic amounts, methods, geo, a ~92% success
rate and a small fraud fraction.

Run:
    PG_DSN=postgresql://payments:payments_secret@localhost:5432/payments \
        python -m data_generator.live_postgres --rate 8 --batch 4
"""
from __future__ import annotations

import argparse
import os
import random
import signal
import sys
import time

import psycopg2
from psycopg2.extras import execute_values

PG_DSN = os.getenv("PG_DSN", "postgresql://payments:payments_secret@localhost:5432/payments")

METHODS = ["upi", "upi", "upi", "debit_card", "credit_card", "wallet", "emi", "qr", "netbanking"]
CHANNELS = ["pos", "online", "ecom", "qr"]
RESP_OK = ["00", "00", "00", "10", "11"]
RESP_FAIL = ["05", "51", "14", "91", "61"]
MCCS = ["5411", "5812", "5541", "5732", "5912", "4814", "5999", "7011", "5651", "4111"]
CITIES = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Pune", "Hyderabad", "Kolkata", "Jaipur"]

_running = True


def _stop(*_):
    global _running
    _running = False


def _load_dims(cur):
    cur.execute("SELECT id, mcc FROM merchant.merchant_master")
    merchants = cur.fetchall()
    cur.execute("SELECT id FROM device.device_master")
    devices = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT id FROM customer.customer_master")
    customers = [r[0] for r in cur.fetchall()]
    if not merchants:
        sys.exit("no merchants in OLTP — seed Postgres first (postgres/apply.sh)")
    cur.execute("SELECT COALESCE(max(substr(merchant_code,2)::int),0) "
                "FROM merchant.merchant_master WHERE merchant_code ~ '^M[0-9]+$'")
    seq = cur.fetchone()[0]
    return merchants, devices, customers, seq


def _onboard_merchant(cur, seq: int):
    """Insert a brand-new merchant and return (id, mcc) so it joins the pool."""
    code = f"M{seq:07d}"
    city = random.choice(CITIES)
    mcc = random.choice(MCCS)
    cur.execute(
        """INSERT INTO merchant.merchant_master
               (merchant_code, legal_name, dba_name, mcc, entity_type, category,
                sales_channel, status, onboarded_date)
           VALUES (%s,%s,%s,%s,'proprietorship','offline','field','active',CURRENT_DATE)
           RETURNING id""",
        (code, f"{city} {mcc} Pvt Ltd", f"{city} {mcc} Store", mcc))
    return cur.fetchone()[0], mcc, code


def _row(merchants, devices, customers):
    mid, mcc = random.choice(merchants)
    success = random.random() > 0.08
    fraud = (not success and random.random() < 0.05) or random.random() < 0.004
    amount = round(random.choice([
        random.uniform(50, 2_000), random.uniform(2_000, 20_000),
        random.uniform(20_000, 90_000)]), 2)
    if fraud:
        amount = round(random.uniform(40_000, 150_000), 2)
    return (
        mid,
        random.choice(devices) if devices and random.random() > 0.05 else None,
        random.choice(customers) if customers and random.random() > 0.05 else None,
        "".join(random.choices("0123456789", k=12)),   # rrn
        random.randint(100000, 999999),                 # stan
        random.choice(METHODS),                         # payment_method
        random.choice(CHANNELS),                        # channel
        mcc,                                            # mcc
        amount,
        success,
        random.choice(RESP_OK if success else RESP_FAIL),
        round(random.uniform(8.0, 34.0), 6),            # latitude (India)
        round(random.uniform(68.0, 92.0), 6),           # longitude
        fraud,
    )


INSERT = """
INSERT INTO txn.transaction_header
    (merchant_id, device_id, customer_id, rrn, stan, payment_method, channel,
     mcc, amount, currency, state, is_success, response_code, latitude, longitude,
     fraud_label, created_at, updated_at)
VALUES %s
"""
TEMPLATE = ("(%s,%s,%s,%s,%s,%s::ref.payment_method,%s,%s,%s,'INR',"
            "%s::ref.txn_state,%s,%s,%s,%s,%s, now(), now())")


def main():
    ap = argparse.ArgumentParser(description="Continuous Postgres transaction generator")
    ap.add_argument("--rate", type=float, default=8, help="batches per second")
    ap.add_argument("--batch", type=int, default=4, help="transactions per batch")
    ap.add_argument("--merchant-every", type=float, default=25,
                    help="onboard a new merchant every N seconds (0 to disable)")
    args = ap.parse_args()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = True
    cur = conn.cursor()
    merchants, devices, customers, seq = _load_dims(cur)
    print(f"live-postgres: {len(merchants)} merchants / {len(devices)} devices / "
          f"{len(customers)} customers loaded; ~{args.rate*args.batch:.0f} txns/sec, "
          f"new merchant every {args.merchant_every}s", flush=True)

    period = 1.0 / args.rate if args.rate > 0 else 0.1
    total = 0
    last_onboard = time.time()
    while _running:
        if args.merchant_every and time.time() - last_onboard >= args.merchant_every:
            try:
                seq += 1
                mid, mcc, code = _onboard_merchant(cur, seq)
                merchants.append((mid, mcc))   # new merchant starts transacting
                print(f"live-postgres: onboarded merchant {code}", flush=True)
            except Exception as exc:
                print(f"live-postgres: onboard error: {exc}", flush=True)
            last_onboard = time.time()
        rows = [_row(merchants, devices, customers) for _ in range(args.batch)]
        states = ["captured" if r[9] else "failed" for r in rows]
        values = [(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8],
                   st, r[9], r[10], r[11], r[12], r[13]) for r, st in zip(rows, states)]
        try:
            execute_values(cur, INSERT, values, template=TEMPLATE)
            total += len(values)
            if total % (args.batch * 25) < args.batch:
                print(f"live-postgres: inserted {total} transactions", flush=True)
        except Exception as exc:  # keep the stream alive across transient errors
            print(f"live-postgres: insert error: {exc}", flush=True)
            time.sleep(1)
        time.sleep(period)

    cur.close(); conn.close()
    print(f"live-postgres: stopped after {total} transactions", flush=True)


if __name__ == "__main__":
    main()
