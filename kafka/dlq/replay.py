"""Replay a DLQ topic: drain `<topic>.dlq`, re-validate, and re-publish the now
-valid events back to the source topic (e.g. after a schema fix or a ClickHouse
outage). Still-invalid messages are left in the DLQ.

    python -m dlq.replay --topic transaction_events --max 1000
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from confluent_kafka import Consumer, Producer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from schemas import TOPICS, validate  # noqa: E402


def replay(topic: str, bootstrap: str, max_msgs: int) -> tuple[int, int]:
    dlq_topic = TOPICS[topic].dlq
    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": f"dlq-replay-{topic}",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
    })
    producer = Producer({"bootstrap.servers": bootstrap})
    consumer.subscribe([dlq_topic])
    key_field = TOPICS[topic].key_field
    replayed = skipped = 0
    empty_polls = 0
    try:
        while replayed + skipped < max_msgs:
            msg = consumer.poll(2.0)
            if msg is None:
                # tolerate initial empty polls while the group is assigned;
                # give up only after several consecutive empties (topic drained).
                empty_polls += 1
                if empty_polls >= 5:
                    break
                continue
            empty_polls = 0
            if msg.error():
                continue
            res = validate(topic, msg.value())
            if res.ok:
                key = str(res.payload.get(key_field, "") or "")
                producer.produce(topic, key=key.encode(), value=msg.value())
                replayed += 1
            else:
                skipped += 1   # still bad; leave it (committed offset moves on)
        producer.flush(10)
    finally:
        consumer.close()
    return replayed, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", required=True, choices=list(TOPICS))
    ap.add_argument("--max", type=int, default=10000)
    ap.add_argument("--bootstrap", default=config.KAFKA_BOOTSTRAP)
    args = ap.parse_args()
    r, s = replay(args.topic, args.bootstrap, args.max)
    print(f"replayed={r} still_invalid={s} from {args.topic}.dlq")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
