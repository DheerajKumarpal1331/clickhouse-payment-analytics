"""Prometheus metrics shared by producer + consumer. Exposed on METRICS_PORT
(/metrics), scraped by the `kafka-pipeline` job in docker/prometheus/prometheus.yml.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, start_http_server

PRODUCED_TOTAL = Counter("events_produced_total", "Events produced", ["topic"])
PRODUCE_ERRORS = Counter("events_produce_errors_total", "Delivery errors", ["topic"])
CONSUMED_TOTAL = Counter("events_consumed_total", "Events consumed", ["topic"])
INSERTED_TOTAL = Counter("events_inserted_total", "Rows inserted to ClickHouse", ["topic"])
DLQ_TOTAL = Counter("events_dlq_total", "Events routed to DLQ", ["topic", "stage"])

CH_INSERT_SECONDS = Histogram("ch_insert_seconds", "ClickHouse batch insert latency", ["topic"])
CONSUMER_LAG = Gauge("consumer_lag", "Consumer lag (messages)", ["topic", "partition"])

_started = False


def start_metrics_server(port: int) -> None:
    global _started
    if not _started:
        start_http_server(port)
        _started = True
