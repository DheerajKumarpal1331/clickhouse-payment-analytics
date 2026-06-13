"""Consumer-group lag reporter: end offset − committed offset per partition,
summed per topic. Prints a snapshot and updates the Prometheus `consumer_lag`
gauge. (kafka-exporter also exposes lag for Grafana; this is a CLI for quick
checks and for feeding the pipeline's own /metrics.)

    python -m monitoring.consumer_lag --group ch-sink
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from confluent_kafka import Consumer, TopicPartition
from confluent_kafka.admin import AdminClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from schemas import ALL_TOPICS  # noqa: E402
from monitoring import metrics  # noqa: E402


def compute_lag(group: str, bootstrap: str, topics: list[str]) -> dict[str, int]:
    admin = AdminClient({"bootstrap.servers": bootstrap})
    md = admin.list_topics(timeout=10)
    consumer = Consumer({"bootstrap.servers": bootstrap, "group.id": group,
                         "enable.auto.commit": False})
    per_topic: dict[str, int] = {}
    try:
        for topic in topics:
            tmd = md.topics.get(topic)
            if tmd is None:
                continue
            tps = [TopicPartition(topic, p) for p in tmd.partitions]
            committed = consumer.committed(tps, timeout=10)
            total = 0
            for tp in committed:
                lo, hi = consumer.get_watermark_offsets(tp, timeout=10, cached=False)
                pos = tp.offset if tp.offset >= 0 else lo
                lag = max(0, hi - pos)
                total += lag
                metrics.CONSUMER_LAG.labels(topic=topic, partition=tp.partition).set(lag)
            per_topic[topic] = total
    finally:
        consumer.close()
    return per_topic


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", default=config.CONSUMER_GROUP)
    ap.add_argument("--bootstrap", default=config.KAFKA_BOOTSTRAP)
    ap.add_argument("--topics", help="comma-separated (default: all)")
    args = ap.parse_args()
    topics = args.topics.split(",") if args.topics else ALL_TOPICS
    lag = compute_lag(args.group, args.bootstrap, topics)
    print(f"{'topic':<22} lag")
    for t, l in sorted(lag.items()):
        print(f"{t:<22} {l}")
    print(f"{'TOTAL':<22} {sum(lag.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
