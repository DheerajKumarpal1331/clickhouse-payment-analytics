"""Poke until a ClickHouse table holds at least ``min_rows`` rows — optionally
restricted to one date via a date column. A freshness gate so feature
generation, mart refreshes, and model training only start once the facts they
read have actually landed (e.g. wait for today's transactions before computing
today's features).

``date_column`` + ``ds`` template a ``WHERE <col> = '<ds>'`` filter; omit them to
gate on the whole table.
"""
from __future__ import annotations

from airflow.sensors.base import BaseSensorOperator
from airflow.utils.decorators import apply_defaults

from operators import clients


class ClickHousePartitionSensor(BaseSensorOperator):
    ui_color = "#dd6b20"
    template_fields = ("ds",)

    @apply_defaults
    def __init__(self, table: str, min_rows: int = 1,
                 date_column: str | None = None, ds: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.table = table
        self.min_rows = min_rows
        self.date_column = date_column
        self.ds = ds

    def poke(self, context) -> bool:
        where = ""
        if self.date_column:
            ds = self.ds or context["ds"]
            where = f" WHERE {self.date_column} = toDate('{ds}')"
        n = clients.ch_scalar(f"SELECT count() FROM {self.table}{where}")
        n = int(n or 0)
        self.log.info("ClickHousePartitionSensor %s%s: %s row(s) (need %s)",
                      self.table, where, n, self.min_rows)
        return n >= self.min_rows
