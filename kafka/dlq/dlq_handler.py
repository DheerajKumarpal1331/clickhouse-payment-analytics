"""Dead-letter handling. A bad event is sent two places:
  1. the `<topic>.dlq` Kafka topic (full payload + error in headers) — durable,
     replayable by dlq/replay.py;
  2. the ClickHouse `dead_letter_events` table — queryable for the Operations
     dashboard / DQ scorecard.
ClickHouse writes are best-effort (over stdlib HTTP) so a DLQ insert failure
never blocks the pipeline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402


class DlqHandler:
    def __init__(self, producer, ch_sink=None):
        self.producer = producer          # reuse the caller's confluent Producer
        self.ch_sink = ch_sink            # optional ClickHouseSink for dead_letter_events

    def send(self, topic: str, payload, error: str, source: str = "consumer") -> None:
        raw = payload if isinstance(payload, (bytes, str)) else json.dumps(payload, default=str)
        raw_bytes = raw.encode() if isinstance(raw, str) else raw
        # 1) durable replayable copy on the DLQ topic
        try:
            self.producer.produce(
                f"{topic}.dlq", value=raw_bytes,
                headers=[("error", error[:480].encode()), ("source", source.encode())])
            self.producer.poll(0)
        except Exception:  # noqa: BLE001 - DLQ must never raise into the hot path
            pass
        # 2) queryable copy in ClickHouse
        if self.ch_sink is not None:
            try:
                self.ch_sink.insert("dead_letter_events", [{
                    "topic": topic,
                    "raw_payload": raw.decode() if isinstance(raw, bytes) else raw,
                    "error": error[:2000],
                    "consumer": source,
                }])
            except Exception:  # noqa: BLE001
                pass
