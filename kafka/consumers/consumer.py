"""Consumer: Kafka -> ClickHouse, with DLQ and at-least-once delivery.

Loop: poll a batch -> validate each message (bad -> DLQ) -> accumulate valid
rows per topic -> flush to ClickHouse in one JSONEachRow insert per topic ->
**commit offsets only after a successful insert**. On a transient ClickHouse
error the batch is retried with backoff; offsets are not committed, so nothing
is lost (at-least-once; ClickHouse de-dups are handled at the OLAP layer where
needed). Flushes also trigger on a time bound so low-volume topics stay fresh.
"""
from __future__ import annotations

import sys
import time
from collections import defaultdict
from pathlib import Path

from confluent_kafka import Consumer, KafkaException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from schemas import TOPICS, validate  # noqa: E402
from dlq.dlq_handler import DlqHandler  # noqa: E402
from monitoring import metrics  # noqa: E402
from consumers.ch_sink import ClickHouseSink, ClickHouseError  # noqa: E402

# a confluent Producer is needed by the DLQ handler to publish to <topic>.dlq
from confluent_kafka import Producer  # noqa: E402


class ChConsumer:
    def __init__(self, topics: list[str], bootstrap: str = config.KAFKA_BOOTSTRAP,
                 ch_url: str = config.CH_URL, ch_db: str = config.CH_DB,
                 group: str = config.CONSUMER_GROUP):
        self.topics = topics
        self.consumer = Consumer({
            "bootstrap.servers": bootstrap,
            "group.id": group,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,           # we commit only after a successful sink
            "max.poll.interval.ms": 300000,
        })
        self.sink = ClickHouseSink(ch_url, ch_db)
        self.dlq = DlqHandler(Producer({"bootstrap.servers": bootstrap}), ch_sink=self.sink)

    def _flush(self, batches: dict[str, list[dict]]) -> None:
        for topic, rows in list(batches.items()):
            if not rows:
                continue
            table = TOPICS[topic].ch_table
            for attempt in range(config.MAX_RETRIES):
                try:
                    with metrics.CH_INSERT_SECONDS.labels(topic=topic).time():
                        self.sink.insert(table, rows)
                    metrics.INSERTED_TOTAL.labels(topic=topic).inc(len(rows))
                    batches[topic] = []
                    break
                except ClickHouseError as e:
                    wait = min(2 ** attempt, 30)
                    print(f"  CH insert {table} failed (try {attempt+1}): {e}; retry in {wait}s")
                    time.sleep(wait)
            else:
                # exhausted retries: DLQ the whole batch so the pipeline can advance
                for r in rows:
                    self.dlq.send(topic, r, "clickhouse insert failed after retries")
                    metrics.DLQ_TOTAL.labels(topic=topic, stage="sink").inc()
                batches[topic] = []

    def run(self) -> None:
        self.consumer.subscribe(self.topics)
        print(f"consumer group={config.CONSUMER_GROUP} topics={self.topics} -> ClickHouse")
        batches: dict[str, list[dict]] = defaultdict(list)
        pending = 0
        last_flush = time.time()
        try:
            while True:
                msg = self.consumer.poll(1.0)
                now = time.time()
                if msg is not None and not msg.error():
                    topic = msg.topic()
                    metrics.CONSUMED_TOTAL.labels(topic=topic).inc()
                    res = validate(topic, msg.value())
                    if res.ok:
                        batches[topic].append(res.payload)
                        pending += 1
                    else:
                        self.dlq.send(topic, msg.value(), res.error or "invalid")
                        metrics.DLQ_TOTAL.labels(topic=topic, stage="consume").inc()
                elif msg is not None and msg.error():
                    raise KafkaException(msg.error())

                if pending >= config.BATCH_SIZE or (pending and (now - last_flush) * 1000 >= config.BATCH_MS):
                    self._flush(batches)
                    self.consumer.commit(asynchronous=False)   # at-least-once
                    pending, last_flush = 0, now
        except KeyboardInterrupt:
            pass
        finally:
            self._flush(batches)
            try:
                self.consumer.commit(asynchronous=False)
            except KafkaException:
                pass
            self.consumer.close()
