"""Poke until a CDC source has rows past its persisted ``(wm, id)`` cursor —
i.e. there is fresh OLTP data worth running ingestion for. Lets an ingestion DAG
wait cheaply for upstream writes instead of running an empty load every minute.

Uses the same cursor and projection registry as PostgresToClickHouseOperator, so
"is there new data?" is asked with exactly the predicate the load will use.
"""
from __future__ import annotations

from airflow.sensors.base import BaseSensorOperator
from airflow.utils.decorators import apply_defaults

from operators import clients
from operators.cdc_queries import CDC_SOURCES


class PostgresRowSensor(BaseSensorOperator):
    ui_color = "#38a169"

    @apply_defaults
    def __init__(self, source: str, min_rows: int = 1, **kwargs):
        super().__init__(**kwargs)
        if source not in CDC_SOURCES:
            raise ValueError(f"unknown CDC source '{source}'")
        self.source = source
        self.min_rows = min_rows

    def poke(self, context) -> bool:
        spec = CDC_SOURCES[self.source]
        wm, last_id = clients.get_watermark(self.source)
        sql = (f"SELECT count(*) AS n FROM ({spec.sql}) s "
               f"WHERE (s._wm > %(wm)s::timestamptz) "
               f"OR (s._wm = %(wm)s::timestamptz AND s._id > %(id)s)")
        rows = clients.pg_fetch(sql, {"wm": wm, "id": last_id})
        n = int(rows[0]["n"]) if rows else 0
        self.log.info("PostgresRowSensor %s: %s new row(s) past cursor (need %s)",
                      self.source, n, self.min_rows)
        return n >= self.min_rows
