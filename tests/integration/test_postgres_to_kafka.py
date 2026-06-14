"""Integration: PostgreSQL -> Kafka.

Two halves of the producer contract against live services:
  1. the per-topic projection SQL actually executes against the real OLTP
     schema and yields the flat event shape (DbSource.fetch);
  2. an event round-trips through a real broker (produce keyed -> consume back).

Gated by RUN_INTEGRATION=1 (see tests/conftest.py).
"""
from __future__ import annotations

import json
import uuid

import pytest

pytestmark = [pytest.mark.integration]


def test_projection_sql_runs_against_live_oltp(pg_dsn):
    """merchant_events projection must execute and expose the cursor columns."""
    from kafka.producers.db_source import DbSource
    src = DbSource(pg_dsn)
    try:
        rows = src.fetch("merchant_events", "1970-01-01 00:00:00", 0, limit=5)
    finally:
        src.close()
    # schema is seeded in Phase 2, so there is at least one merchant
    assert rows, "no merchants found in OLTP — is the schema seeded?"
    r = rows[0]
    assert "merchant_id" in r and "_id" in r and "_wm" in r


def test_cursor_advances_monotonically(pg_dsn):
    """Fetching past the previous (wm,id) returns strictly newer rows."""
    from kafka.producers.db_source import DbSource, split_cursor_fields
    src = DbSource(pg_dsn)
    try:
        first = src.fetch("transaction_events", "1970-01-01 00:00:00", 0, limit=10)
        if len(first) < 2:
            pytest.skip("not enough transactions seeded to test cursor advance")
        _, wm, last_id = split_cursor_fields(dict(first[0]))
        nxt = src.fetch("transaction_events", wm, last_id, limit=10)
    finally:
        src.close()
    # the row we used as the cursor must not reappear
    seen = {str(r["_id"]) for r in nxt}
    assert str(last_id) not in seen


def test_event_roundtrips_through_kafka(kafka_bootstrap):
    from confluent_kafka import Producer, Consumer
    from confluent_kafka.admin import AdminClient, NewTopic
    topic = f"itest_pg_to_kafka_{uuid.uuid4().hex[:8]}"
    key = "M1"
    payload = {"merchant_id": key, "event_time": "2026-06-14 12:00:00",
               "status": "active", "mcc": "5411"}

    # broker auto-create is off by design, so create the scratch topic explicitly
    admin = AdminClient({"bootstrap.servers": kafka_bootstrap})
    for _t, fut in admin.create_topics(
            [NewTopic(topic, num_partitions=1, replication_factor=1)]).items():
        fut.result(timeout=15)

    producer = Producer({"bootstrap.servers": kafka_bootstrap})
    producer.produce(topic, key=key.encode(), value=json.dumps(payload).encode())
    assert producer.flush(15) == 0, "messages still queued — broker unreachable?"

    consumer = Consumer({
        "bootstrap.servers": kafka_bootstrap,
        "group.id": f"itest_{uuid.uuid4().hex[:8]}",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    consumer.subscribe([topic])
    got = None
    try:
        for _ in range(50):  # poll up to ~10s
            msg = consumer.poll(0.2)
            if msg is None or msg.error():
                continue
            got = (msg.key().decode(), json.loads(msg.value()))
            break
    finally:
        consumer.close()
        admin.delete_topics([topic])  # cleanup scratch topic

    assert got is not None, "did not receive the produced message"
    assert got[0] == key
    assert got[1]["merchant_id"] == key
