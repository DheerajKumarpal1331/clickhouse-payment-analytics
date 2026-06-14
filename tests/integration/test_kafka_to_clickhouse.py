"""Integration: Kafka -> ClickHouse.

Exercises the consumer's sink contract against a live ClickHouse:
  - the HTTP sink connects (ping);
  - a wide fact event lands in fact_transactions via FORMAT JSONEachRow with the
    consumer's tolerant settings (unknown fields skipped, defaults applied);
  - the row is queryable back by its id.

Gated by RUN_INTEGRATION=1 (see tests/conftest.py).
"""
from __future__ import annotations

import base64
import urllib.parse
import urllib.request
import uuid

import pytest

pytestmark = [pytest.mark.integration]


def _ch_scalar(ch_url: str, ch_db: str, sql: str) -> str:
    p = urllib.parse.urlparse(ch_url)
    base = f"{p.scheme}://{p.hostname}:{p.port or 8123}"
    params = urllib.parse.urlencode({"query": sql, "database": ch_db})
    req = urllib.request.Request(f"{base}/?{params}")
    cred = f"{p.username or 'default'}:{p.password or ''}"
    req.add_header("Authorization", "Basic " + base64.b64encode(cred.encode()).decode())
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode().strip()


def test_sink_pings_live_clickhouse(ch_url, ch_db):
    from kafka.consumers.ch_sink import ClickHouseSink
    assert ClickHouseSink(ch_url, ch_db).ping() is True


def test_event_lands_in_fact_transactions(ch_url, ch_db):
    from kafka.consumers.ch_sink import ClickHouseSink
    sink = ClickHouseSink(ch_url, ch_db)
    txn_id = f"ITEST{uuid.uuid4().hex[:12]}"
    # a narrow CDC-shaped event; columns the table lacks here take DDL defaults
    event = {
        "transaction_id": txn_id,
        "merchant_id": "M1",
        "event_time": "2026-06-14 12:00:00",
        "amount": 123.45,
        "currency": "INR",
        "is_success": 1,
        "fraud_label": 0,
        "unknown_field_should_be_skipped": "x",
    }
    n = sink.insert("fact_transactions", [event])
    assert n == 1

    count = _ch_scalar(ch_url, ch_db,
                       f"SELECT count() FROM {ch_db}.fact_transactions "
                       f"WHERE transaction_id = '{txn_id}'")
    assert count == "1"


def test_dlq_event_is_queryable(ch_url, ch_db):
    """The DLQ ClickHouse copy (Operations dashboard / DQ scorecard) round-trips."""
    from kafka.consumers.ch_sink import ClickHouseSink
    from kafka.dlq.dlq_handler import DlqHandler

    class _NoopProducer:
        def produce(self, *a, **k): pass
        def poll(self, _): pass

    sink = ClickHouseSink(ch_url, ch_db)
    marker = f"itest-{uuid.uuid4().hex[:10]}"
    DlqHandler(_NoopProducer(), ch_sink=sink).send(
        "transaction_events", {"marker": marker}, "itest synthetic error")

    count = _ch_scalar(ch_url, ch_db,
                       f"SELECT count() FROM {ch_db}.dead_letter_events "
                       f"WHERE raw_payload LIKE '%{marker}%'")
    assert int(count) >= 1
