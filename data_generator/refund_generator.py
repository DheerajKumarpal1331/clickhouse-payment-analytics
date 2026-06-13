"""Refund & chargeback generator. Both are downstream of a transaction:
a refund returns money on a successful sale; a chargeback is a customer
dispute that lands days to weeks later. Refund-abuse fraud surfaces here as
a near-instant, full-value refund.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta

REFUND_REASONS = ["item_not_received", "duplicate", "customer_request"]
CHARGEBACK_REASON_CODES = ["10.4", "13.1", "13.2", "4837", "4853"]


def make_refund(rng: random.Random, txn: dict, abusive: bool = False) -> dict:
    """Build a refund for a (successful) transaction.

    Abusive refunds are fast (minutes) and full-value — the refund_abuse
    fraud signature; legitimate refunds are slower and often partial.
    """
    delay = timedelta(minutes=rng.randint(5, 60)) if abusive else timedelta(days=rng.randint(1, 7))
    ts = datetime.strptime(txn["event_time"][:19], "%Y-%m-%d %H:%M:%S") + delay
    amount = txn["amount"] if abusive else round(txn["amount"] * rng.uniform(0.3, 1.0), 2)
    return {
        "refund_id": f"R{uuid.UUID(int=rng.getrandbits(128)).hex[:16].upper()}",
        "transaction_id": txn["transaction_id"],
        "rrn": txn.get("rrn", ""),
        "merchant_id": txn["merchant_id"],
        "customer_id": txn["customer_id"],
        "event_time": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "requested_time": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "processed_time": (ts + timedelta(minutes=rng.randint(1, 120))).strftime("%Y-%m-%d %H:%M:%S"),
        "amount": amount,
        "original_amount": txn["amount"],
        "is_partial": int(amount < txn["amount"]),
        "refund_type": "online",
        "reason": "customer_request" if not abusive else rng.choice(REFUND_REASONS),
        "reason_detail": "",
        "initiated_by": "customer" if abusive else rng.choices(
            ["merchant", "customer", "ops"], weights=[0.7, 0.25, 0.05])[0],
        "status": "processed",
        "arn": f"74{rng.randint(10**19, 10**20 - 1)}",
        "is_abusive": int(abusive),
    }


def make_chargeback(rng: random.Random, txn: dict) -> dict:
    """Build a chargeback (dispute) raised days/weeks after the transaction."""
    txn_ts = datetime.strptime(txn["event_time"][:19], "%Y-%m-%d %H:%M:%S")
    ts = txn_ts + timedelta(days=rng.randint(3, 45))
    reason_code = rng.choice(CHARGEBACK_REASON_CODES)
    return {
        "chargeback_id": f"CB{uuid.UUID(int=rng.getrandbits(128)).hex[:16].upper()}",
        "transaction_id": txn["transaction_id"],
        "rrn": txn.get("rrn", ""),
        "merchant_id": txn["merchant_id"],
        "customer_id": txn["customer_id"],
        "event_time": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "txn_time": txn_ts.strftime("%Y-%m-%d %H:%M:%S"),
        "amount": txn["amount"],
        "dispute_amount": txn["amount"],
        "reason_code": reason_code,
        "reason_category": "fraud" if reason_code in ("10.4", "4837") else "service",
        "network": txn.get("card_network", "") or "upi",
        "stage": "first_chargeback",
        "status": rng.choices(["open", "won", "lost"], weights=[0.3, 0.3, 0.4])[0],
        "respond_by_date": (ts + timedelta(days=7)).strftime("%Y-%m-%d"),
        "evidence_submitted": int(rng.random() < 0.6),
        "liability": rng.choices(["merchant", "issuer", "acquirer"], weights=[0.6, 0.3, 0.1])[0],
        "recovered_amount": 0,
    }
