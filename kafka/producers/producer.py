"""CDC producer: Postgres -> Kafka.

For each topic, reads the next slice past the persisted cursor, validates each
row against the topic schema, and produces it keyed by the topic's key field
(so a merchant's events stay ordered on one partition). Rows that fail
validation are sent to the DLQ rather than dropped. The cursor only advances
after the slice is queued, and we flush+poll so delivery errors surface.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from confluent_kafka import Producer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from schemas import TOPICS, validate  # noqa: E402
from dlq.dlq_handler import DlqHandler  # noqa: E402
from monitoring import metrics  # noqa: E402
from producers.db_source import DbSource, OffsetStore, split_cursor_fields  # noqa: E402


class CdcProducer:
    def __init__(self, bootstrap: str = config.KAFKA_BOOTSTRAP, dsn: str = config.PG_DSN):
        self.producer = Producer({
            "bootstrap.servers": bootstrap,
            "linger.ms": 20, "batch.num.messages": 10000,
            "compression.type": "lz4", "enable.idempotence": True,
        })
        self.source = DbSource(dsn)
        self.offsets = OffsetStore()
        self.dlq = DlqHandler(self.producer)

    def _delivery(self, err, msg):
        if err is not None:
            metrics.PRODUCE_ERRORS.labels(topic=msg.topic()).inc()

    def poll_topic(self, topic: str, batch: int = config.PRODUCER_BATCH) -> int:
        spec = TOPICS[topic]
        wm, last_id = self.offsets.get(topic)
        rows = self.source.fetch(topic, wm, last_id, batch)
        produced = 0
        for row in rows:
            event, wm, last_id = split_cursor_fields(row)
            res = validate(topic, event)
            if not res.ok:
                self.dlq.send(topic, event, res.error or "validation failed", source="producer")
                metrics.DLQ_TOTAL.labels(topic=topic, stage="produce").inc()
                continue
            key = str(event.get(spec.key_field, "") or "")
            self.producer.produce(topic, key=key.encode(),
                                  value=json.dumps(event, default=str).encode(),
                                  on_delivery=self._delivery)
            produced += 1
            metrics.PRODUCED_TOTAL.labels(topic=topic).inc()
        self.producer.poll(0)
        self.producer.flush(10)
        if rows:
            self.offsets.set(topic, wm, last_id)   # advance only after flush
        return produced

    def run(self, topics: list[str], once: bool = False,
            interval: float = config.POLL_INTERVAL_SEC):
        print(f"producer: {len(topics)} topic(s) -> {config.KAFKA_BOOTSTRAP}")
        while True:
            total = sum(self.poll_topic(t) for t in topics)
            if total:
                print(f"  produced {total} events")
            if once:
                return total
            if total == 0:
                time.sleep(interval)

    def close(self):
        self.producer.flush(10)
        self.source.close()
