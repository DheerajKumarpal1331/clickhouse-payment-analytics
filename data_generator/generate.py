"""CLI orchestrator for the synthetic payment ecosystem.

Modes
-----
historical : write Parquet (dims + partitioned transaction parts + refunds +
             chargebacks) for ClickHouse backfill.
stream     : produce live events into Kafka at a target rate (500-5000/sec).

Examples
--------
# 10M transactions across 365 days into ./data (single process)
python generate.py historical --transactions 10_000_000 --days 365 --out ./data

# Full portfolio scale with 8 worker processes
python generate.py historical --transactions 100_000_000 --days 1095 \
    --merchants 100000 --customers 5000000 --out ./data --workers 8

# Live stream at 1000 events/sec into Kafka
python generate.py stream --rate 1000 --bootstrap localhost:9092
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta

import pyarrow as pa
import pyarrow.parquet as pq

from merchant_generator import generate_merchants, to_dicts as merchants_to_dicts
from customer_generator import generate_customers, to_dicts as customers_to_dicts
from device_generator import generate_devices, to_dicts as devices_to_dicts
from transaction_generator import TransactionGenerator
from refund_generator import make_refund, make_chargeback

BATCH_ROWS = 500_000


def build_world(n_merchants: int, n_customers: int, seed: int):
    merchants = generate_merchants(n_merchants, seed)
    customers = generate_customers(n_customers, seed + 1)
    devices = generate_devices(merchants, seed + 2)
    return merchants, customers, devices


def _emit_downstream(gen, txn, refunds, chargebacks):
    """Probabilistically spin refunds/chargebacks off a successful txn."""
    r = gen.rng.random()
    if not txn["is_success"]:
        return
    if txn["fraud_scenario"] == "refund_abuse" or r < 0.015:
        refunds.append(make_refund(gen.rng, txn, abusive=txn["fraud_scenario"] == "refund_abuse"))
    if (txn["fraud_label"] and r < 0.35) or (not txn["fraud_label"] and r < 0.001):
        chargebacks.append(make_chargeback(gen.rng, txn))


def _generate_transactions(gen, start, end, target, out, prefix=""):
    """Stream transactions to partitioned parquet; return (txns, refunds, cbs)."""
    buf, refunds, chargebacks, part = [], [], [], 0
    t0 = time.time()
    n = 0
    for txn in gen.stream(start, end, target):
        buf.append(txn)
        n += 1
        _emit_downstream(gen, txn, refunds, chargebacks)
        if len(buf) >= BATCH_ROWS:
            pq.write_table(pa.Table.from_pylist(buf), f"{out}/transactions_{prefix}{part:04d}.parquet")
            print(f"  {prefix}part {part}: {n:,} txns ({n / max(time.time() - t0, 1):,.0f}/s)")
            buf, part = [], part + 1
    if buf:
        pq.write_table(pa.Table.from_pylist(buf), f"{out}/transactions_{prefix}{part:04d}.parquet")
    if refunds:
        pq.write_table(pa.Table.from_pylist(refunds), f"{out}/refunds_{prefix}.parquet")
    if chargebacks:
        pq.write_table(pa.Table.from_pylist(chargebacks), f"{out}/chargebacks_{prefix}.parquet")
    return n, len(refunds), len(chargebacks)


def _worker(payload):
    """Multiprocessing entry: rebuild the deterministic world, generate a slice."""
    wid, n_txns, days, out, n_merchants, n_customers, seed, fraud_rate = payload
    merchants, customers, devices = build_world(n_merchants, n_customers, seed)
    gen = TransactionGenerator(merchants, customers, devices, fraud_rate=fraud_rate, seed=seed + 100 + wid)
    end = datetime.now().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    return _generate_transactions(gen, start, end, n_txns, out, prefix=f"w{wid}_")


def cmd_historical(args):
    os.makedirs(args.out, exist_ok=True)
    merchants, customers, devices = build_world(args.merchants, args.customers, args.seed)

    # dimensions (written once)
    for name, rows in (("merchants", merchants_to_dicts(merchants)),
                       ("customers", customers_to_dicts(customers)),
                       ("devices", devices_to_dicts(devices))):
        pq.write_table(pa.Table.from_pylist(rows), f"{args.out}/dim_{name}.parquet")
        print(f"wrote dim_{name}.parquet ({len(rows):,} rows)")

    t0 = time.time()
    if args.workers > 1:
        from multiprocessing import Pool
        per = args.transactions // args.workers
        payloads = [(w, per, args.days, args.out, args.merchants, args.customers, args.seed, args.fraud_rate)
                    for w in range(args.workers)]
        print(f"spawning {args.workers} workers × {per:,} txns ...")
        with Pool(args.workers) as pool:
            results = pool.map(_worker, payloads)
        txns = sum(r[0] for r in results); refs = sum(r[1] for r in results); cbs = sum(r[2] for r in results)
    else:
        gen = TransactionGenerator(merchants, customers, devices, fraud_rate=args.fraud_rate, seed=args.seed)
        end = datetime.now().replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(days=args.days)
        txns, refs, cbs = _generate_transactions(gen, start, end, args.transactions, args.out)

    print(f"done: {txns:,} txns, {refs:,} refunds, {cbs:,} chargebacks in {time.time() - t0:,.0f}s")


def cmd_stream(args):
    from confluent_kafka import Producer  # lazy import so historical mode needs no broker

    merchants, customers, devices = build_world(args.merchants, args.customers, args.seed)
    gen = TransactionGenerator(merchants, customers, devices, fraud_rate=args.fraud_rate, seed=args.seed)
    producer = Producer({
        "bootstrap.servers": args.bootstrap,
        "linger.ms": 20, "batch.num.messages": 5000, "compression.type": "lz4",
    })

    sent, t0 = 0, time.time()
    start = datetime.now()
    try:
        for txn in gen.stream(start, start + timedelta(days=365), 10**12):
            txn["event_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            producer.produce("transaction_events", key=txn["merchant_id"], value=json.dumps(txn).encode())
            if txn["is_success"] and gen.rng.random() < 0.01:
                producer.produce("refund_events", value=json.dumps(make_refund(gen.rng, txn)).encode())
            sent += 1
            if sent % args.rate == 0:
                producer.poll(0)
                sleep_for = sent / args.rate - (time.time() - t0)
                if sleep_for > 0:
                    time.sleep(sleep_for)
                if sent % (args.rate * 10) == 0:
                    print(f"{sent:,} events @ {sent / (time.time() - t0):,.0f}/s")
    except KeyboardInterrupt:
        pass
    finally:
        producer.flush(10)
        print(f"flushed, total sent: {sent:,}")


def main():
    p = argparse.ArgumentParser(description="Synthetic payment ecosystem generator")
    sub = p.add_subparsers(dest="cmd", required=True)
    common = dict(merchants=5000, customers=200_000, fraud_rate=0.004, seed=42)

    h = sub.add_parser("historical")
    h.add_argument("--transactions", type=lambda s: int(s.replace("_", "")), default=10_000_000)
    h.add_argument("--days", type=int, default=365)
    h.add_argument("--out", default="./data")
    h.add_argument("--workers", type=int, default=1)
    s = sub.add_parser("stream")
    s.add_argument("--rate", type=int, default=1000, help="events/sec (500-5000)")
    s.add_argument("--bootstrap", default="localhost:9092")

    for sp in (h, s):
        for k, v in common.items():
            sp.add_argument(f"--{k.replace('_', '-')}", type=type(v), default=v, dest=k)

    args = p.parse_args()
    {"historical": cmd_historical, "stream": cmd_stream}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
