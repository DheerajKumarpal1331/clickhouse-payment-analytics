"""Load test — sustained Kafka ingest throughput (target: 5000 events/sec).

Produces a burst of synthetic transaction events to a scratch topic with the
producer tuned the way the CDC producer is (idempotent, lz4, batched) and
reports achieved events/sec. Run as a script for a full benchmark, or under
pytest (marked `load`, gated by RUN_LOAD=1) for a short throughput assertion.

Script:
    python tests/load/kafka_load.py --count 200000 --rate-target 5000
Pytest:
    RUN_LOAD=1 RUN_INTEGRATION=1 pytest -c tests/pytest.ini tests/load/kafka_load.py
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
import uuid

TARGET_RATE = 5000  # events/sec (Phase 12 spec)


def _event() -> bytes:
    return json.dumps({
        "transaction_id": f"L{random.randint(1, 1_000_000_000)}",
        "merchant_id": f"M{random.randint(1, 1000)}",
        "customer_id": f"C{random.randint(1, 100000)}",
        "amount": round(random.uniform(50, 25_000), 2),
        "currency": "INR",
        "payment_method": "upi",
        "is_success": 1,
        "event_time": "2026-06-14 12:00:00",
    }).encode()


def _ensure_topic(bootstrap: str, topic: str, partitions: int = 6) -> None:
    """Broker auto-create is off by design — create the scratch topic."""
    from confluent_kafka.admin import AdminClient, NewTopic
    admin = AdminClient({"bootstrap.servers": bootstrap})
    for _t, fut in admin.create_topics(
            [NewTopic(topic, num_partitions=partitions, replication_factor=1)]).items():
        try:
            fut.result(timeout=20)
        except Exception:  # noqa: BLE001 - already exists is fine
            pass


def run(bootstrap: str, topic: str, count: int) -> float:
    """Produce `count` events as fast as the client allows; return events/sec."""
    from confluent_kafka import Producer
    _ensure_topic(bootstrap, topic)
    p = Producer({
        "bootstrap.servers": bootstrap,
        "linger.ms": 20, "batch.num.messages": 10000,
        "compression.type": "lz4", "enable.idempotence": True,
        "queue.buffering.max.messages": 1_000_000,
    })
    start = time.perf_counter()
    for i in range(count):
        while True:
            try:
                p.produce(topic, key=str(i % 1000).encode(), value=_event())
                break
            except BufferError:
                p.poll(0.05)  # local queue full — let it drain
        if i % 10000 == 0:
            p.poll(0)
    p.flush(60)
    elapsed = time.perf_counter() - start
    return count / elapsed if elapsed else float("inf")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", default=os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"))
    ap.add_argument("--topic", default=f"loadtest_{uuid.uuid4().hex[:8]}")
    ap.add_argument("--count", type=int, default=200_000)
    ap.add_argument("--rate-target", type=int, default=TARGET_RATE)
    args = ap.parse_args()

    print(f"Producing {args.count:,} events to {args.topic} on {args.bootstrap} ...")
    rate = run(args.bootstrap, args.topic, args.count)
    status = "PASS" if rate >= args.rate_target else "BELOW TARGET"
    print(f"Throughput: {rate:,.0f} events/sec  (target {args.rate_target:,}) -> {status}")


# --------------------------- pytest entry point ------------------------------
def test_throughput_meets_target():
    bootstrap = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
    topic = f"loadtest_{uuid.uuid4().hex[:8]}"
    rate = run(bootstrap, topic, count=50_000)
    print(f"\nachieved {rate:,.0f} events/sec")
    assert rate >= TARGET_RATE, f"throughput {rate:,.0f}/s below target {TARGET_RATE}/s"


try:  # apply markers only when pytest is the runner
    import pytest
    pytestmark = [pytest.mark.load, pytest.mark.integration]
except ImportError:  # pragma: no cover - script mode
    pass


if __name__ == "__main__":
    main()
