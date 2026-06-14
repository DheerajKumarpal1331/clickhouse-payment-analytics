"""Unit tests for the ETL plane (Kafka producers / consumers / DLQ) — no infra.

Exercises the pure logic the streaming pipeline depends on: the per-topic
projection queries, the watermark cursor, the ClickHouse sink's request
assembly, the DLQ fan-out, and event-schema validation.
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest

pytestmark = pytest.mark.unit

ALL_TOPICS = {
    "transaction_events", "refund_events", "chargeback_events", "settlement_events",
    "fraud_events", "support_events", "merchant_events", "device_events",
}


# --------------------------- projection queries ------------------------------
def test_every_topic_has_a_projection_query():
    from kafka.producers.queries import QUERIES
    assert set(QUERIES) == ALL_TOPICS


def test_queries_expose_cursor_columns_and_no_clauses():
    """db_source appends WHERE/ORDER/LIMIT, so the base SQL must omit them and
    must project the cursor metadata (_id, _wm) the reader pops off."""
    from kafka.producers.queries import QUERIES
    for topic, q in QUERIES.items():
        sql = q.sql.lower()
        assert "as _id" in sql, topic
        assert "as _wm" in sql, topic
        assert " where " not in sql, topic
        assert "order by" not in sql, topic
        assert "limit" not in sql, topic
        # watermark / pk expressions are referenced in the projection
        assert q.wm and q.idc


def test_queries_carry_external_codes_not_internal_fks():
    """Events key on merchant_code (external), never the BIGINT FK."""
    from kafka.producers.queries import QUERIES
    for topic, q in QUERIES.items():
        if "merchant_master" in q.sql:
            assert "merchant_code" in q.sql, topic


# ------------------------------ watermark cursor -----------------------------
def test_offset_store_roundtrip(tmp_path):
    from kafka.producers.db_source import OffsetStore, EPOCH
    store = OffsetStore(str(tmp_path / "offsets.json"))
    assert store.get("transaction_events") == (EPOCH, 0)  # cold start
    store.set("transaction_events", "2026-06-14 10:00:00", 42)
    # persisted across instances (restart resumes where it left off)
    reopened = OffsetStore(str(tmp_path / "offsets.json"))
    assert reopened.get("transaction_events") == ("2026-06-14 10:00:00", 42)


def test_split_cursor_fields_pops_metadata():
    from kafka.producers.db_source import split_cursor_fields
    row = {"merchant_id": "M1", "amount": 10.0,
           "_id": "99", "_wm": datetime(2026, 6, 14, 10, 0, 0)}
    event, wm_iso, rid = split_cursor_fields(row)
    assert "_id" not in event and "_wm" not in event
    assert event == {"merchant_id": "M1", "amount": 10.0}
    assert rid == 99
    assert wm_iso.startswith("2026-06-14 10:00:00")


def test_split_cursor_fields_handles_string_watermark():
    from kafka.producers.db_source import split_cursor_fields
    _, wm_iso, rid = split_cursor_fields({"_id": 1, "_wm": "2026-01-01 00:00:00"})
    assert wm_iso == "2026-01-01 00:00:00" and rid == 1


# ----------------------------- ClickHouse sink -------------------------------
def test_sink_parses_url_and_credentials():
    from kafka.consumers.ch_sink import ClickHouseSink
    s = ClickHouseSink("http://analytics:secret@clickhouse:8123", "payments")
    assert s.base == "http://clickhouse:8123"
    assert s.auth == ("analytics", "secret")
    assert s.database == "payments"


def test_sink_empty_insert_is_noop():
    from kafka.consumers.ch_sink import ClickHouseSink
    s = ClickHouseSink("http://u:p@h:8123", "payments")
    assert s.insert("fact_transactions", []) == 0


def test_sink_builds_jsoneachrow_body(monkeypatch):
    from kafka.consumers import ch_sink
    s = ch_sink.ClickHouseSink("http://u:p@h:8123", "payments")
    captured = {}

    def fake_post(query, body):
        captured["query"] = query
        captured["body"] = body

    monkeypatch.setattr(s, "_post", fake_post)
    n = s.insert("fact_transactions", [{"a": 1}, {"a": 2}])
    assert n == 2
    assert captured["query"] == "INSERT INTO payments.fact_transactions FORMAT JSONEachRow"
    lines = captured["body"].decode().splitlines()
    assert [json.loads(line) for line in lines] == [{"a": 1}, {"a": 2}]


# --------------------------------- DLQ ---------------------------------------
class _FakeProducer:
    def __init__(self):
        self.produced = []

    def produce(self, topic, value=None, headers=None):
        self.produced.append({"topic": topic, "value": value, "headers": dict(headers or [])})

    def poll(self, _):
        pass


def test_dlq_routes_to_dlq_topic_with_error_header():
    from kafka.dlq.dlq_handler import DlqHandler
    p = _FakeProducer()
    DlqHandler(p).send("transaction_events", {"bad": True}, "schema: missing amount")
    assert len(p.produced) == 1
    msg = p.produced[0]
    assert msg["topic"] == "transaction_events.dlq"
    assert json.loads(msg["value"]) == {"bad": True}
    assert b"schema" in msg["headers"]["error"]


def test_dlq_also_writes_clickhouse_when_sink_present():
    from kafka.dlq.dlq_handler import DlqHandler

    class _Sink:
        def __init__(self): self.rows = []
        def insert(self, table, rows): self.rows.append((table, rows)); return len(rows)

    sink = _Sink()
    DlqHandler(_FakeProducer(), ch_sink=sink).send("refund_events", "raw-bytes", "boom")
    assert sink.rows[0][0] == "dead_letter_events"
    assert sink.rows[0][1][0]["topic"] == "refund_events"


def test_dlq_never_raises_into_hot_path():
    """A failing producer/sink must be swallowed — the DLQ is the safety net,
    it can't itself take down the consumer."""
    from kafka.dlq.dlq_handler import DlqHandler

    class _BoomProducer:
        def produce(self, *a, **k): raise RuntimeError("kafka down")
        def poll(self, _): pass

    class _BoomSink:
        def insert(self, *a, **k): raise RuntimeError("ch down")

    # should not raise
    DlqHandler(_BoomProducer(), ch_sink=_BoomSink()).send("t", {"x": 1}, "err")


# ----------------------------- schema validation -----------------------------
def test_valid_transaction_event_passes():
    from kafka.schemas.validate import validate
    good = {"transaction_id": "T123456", "merchant_id": "M1",
            "event_time": "2026-06-14 12:00:00", "amount": 499.0,
            "payment_method": "upi", "is_success": 1}
    r = validate("transaction_events", good)
    assert r.ok and r.payload["merchant_id"] == "M1"


def test_invalid_event_is_rejected_with_error():
    from kafka.schemas.validate import validate
    r = validate("transaction_events", {"merchant_id": "M1"})  # missing required fields
    assert not r.ok and r.error
