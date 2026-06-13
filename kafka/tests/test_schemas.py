"""Schema + registry tests (no infra required).

Run:  python -m pytest kafka/tests/test_schemas.py
  or: python kafka/tests/test_schemas.py   (plain-assert fallback)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemas import TOPICS, ALL_TOPICS, validate  # noqa: E402


def test_registry_has_eight_topics():
    assert len(ALL_TOPICS) == 8
    assert set(ALL_TOPICS) == {
        "transaction_events", "refund_events", "chargeback_events", "settlement_events",
        "fraud_events", "support_events", "merchant_events", "device_events"}
    # every spec has a distinct dlq + ch sink
    assert len({t.dlq for t in TOPICS.values()}) == 8
    assert all(t.ch_table for t in TOPICS.values())


def test_valid_transaction_passes():
    good = {"transaction_id": "T123456", "merchant_id": "M1", "event_time": "2026-06-13 12:00:00",
            "amount": 499.0, "payment_method": "upi", "is_success": 1}
    r = validate("transaction_events", good)
    assert r.ok and r.payload["merchant_id"] == "M1"


def test_enriched_superset_passes():
    # gateway hot-path payload with extra fields must still validate (extra=allow)
    wide = {"transaction_id": "T999999", "merchant_id": "M2", "event_time": "2026-06-13 12:00:00.123",
            "amount": 1500.5, "payment_method": "card", "is_success": 1,
            "card_bin": "421323", "emv_tvr": "0102030405", "mdr_amount": 27.0, "auth_latency_ms": 240}
    r = validate("transaction_events", wide)
    assert r.ok and r.payload["card_bin"] == "421323"


def test_bad_events_route_to_dlq():
    cases = [
        {"transaction_id": "T1", "merchant_id": "M", "event_time": "2026-06-13 12:00:00",
         "amount": -5, "payment_method": "upi", "is_success": 1},          # negative amount
        {"transaction_id": "T1", "merchant_id": "M", "event_time": "2026-06-13 12:00:00",
         "amount": 10, "payment_method": "crypto", "is_success": 1},        # bad method
        {"transaction_id": "T1", "merchant_id": "M", "event_time": "not-a-date",
         "amount": 10, "payment_method": "upi", "is_success": 1},           # bad timestamp
        {"merchant_id": "M", "amount": 10, "payment_method": "upi",
         "event_time": "2026-06-13 12:00:00", "is_success": 1},             # missing txn id
    ]
    for c in cases:
        assert validate("transaction_events", c).ok is False


def test_unknown_topic_rejected():
    assert validate("nope_events", {"x": 1}).ok is False


def test_malformed_json_rejected():
    assert validate("transaction_events", b"{not json").ok is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} schema tests passed")
