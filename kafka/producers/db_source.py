"""Incremental Postgres reader (watermark CDC).

Polls each source table for rows past a persisted cursor `(watermark, id)`,
ordered by `(watermark, id)` so same-timestamp rows are never skipped or
duplicated at the boundary. The cursor is persisted per topic in a JSON offset
file, so a restarted producer resumes where it left off.

This is the no-Debezium pattern: simple, self-contained, and correct for
append-mostly tables + updated_at-touched dimensions. Swap in Debezium/logical
decoding for production-grade CDC without changing the producer/consumer.
"""
from __future__ import annotations

import json
from pathlib import Path

import psycopg2
import psycopg2.extras

from .queries import QUERIES

EPOCH = "1970-01-01 00:00:00"


class OffsetStore:
    """Per-topic {topic: {"wm": iso, "id": int}} persisted to a JSON file."""

    def __init__(self, path: str = ".kafka_offsets.json"):
        self.path = Path(path)
        self._data: dict[str, dict] = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text())

    def get(self, topic: str) -> tuple[str, int]:
        c = self._data.get(topic, {})
        return c.get("wm", EPOCH), int(c.get("id", 0))

    def set(self, topic: str, wm: str, id_: int) -> None:
        self._data[topic] = {"wm": wm, "id": id_}
        self.path.write_text(json.dumps(self._data, indent=2))


class DbSource:
    def __init__(self, dsn: str):
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = True

    def fetch(self, topic: str, wm: str, last_id: int, limit: int) -> list[dict]:
        q = QUERIES[topic]
        sql = (f"{q.sql} WHERE ({q.wm} > %(wm)s::timestamptz) "
               f"OR ({q.wm} = %(wm)s::timestamptz AND {q.idc} > %(id)s) "
               f"ORDER BY {q.wm}, {q.idc} LIMIT %(limit)s")
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, {"wm": wm, "id": last_id, "limit": limit})
            return [dict(r) for r in cur.fetchall()]

    def close(self):
        self.conn.close()


def split_cursor_fields(row: dict) -> tuple[dict, str, int]:
    """Pop the cursor metadata (_wm, _id) and return (event, wm_iso, id)."""
    rid = int(row.pop("_id"))
    wm = row.pop("_wm")
    wm_iso = wm.strftime("%Y-%m-%d %H:%M:%S.%f") if hasattr(wm, "strftime") else str(wm)
    return row, wm_iso, rid
