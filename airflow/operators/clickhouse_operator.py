"""Run one or more SQL statements on ClickHouse.

Used to drive the warehouse's own compute from Airflow: feature-store
``INSERT ... SELECT`` materializations, mart refreshes, ``OPTIMIZE ... FINAL``,
and TTL/partition maintenance. Statements run in order; a list is convenient for
a multi-step materialization (e.g. online then offline features) as one task.

``sql`` may be a single string, a list of strings, or a ``.sql`` file path
(resolved against ``sql_dir``) — files are split on ``;`` so a whole feature or
mart script can be applied as one task.
"""
from __future__ import annotations

import os

from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults

from operators import clients


def _split_statements(text: str) -> list[str]:
    return [s.strip() for s in text.split(";") if s.strip()]


class ClickHouseOperator(BaseOperator):
    ui_color = "#ecc94b"
    template_fields = ("sql",)

    @apply_defaults
    def __init__(self, sql, sql_dir: str | None = None, timeout: int = 600, **kwargs):
        super().__init__(**kwargs)
        self.sql = sql
        self.sql_dir = sql_dir
        self.timeout = timeout

    def _statements(self) -> list[str]:
        if isinstance(self.sql, (list, tuple)):
            items = list(self.sql)
        else:
            items = [self.sql]
        out: list[str] = []
        for item in items:
            if item.strip().lower().endswith(".sql"):
                path = os.path.join(self.sql_dir, item) if self.sql_dir else item
                with open(path) as fh:
                    out.extend(_split_statements(fh.read()))
            else:
                out.extend(_split_statements(item))
        return out

    def execute(self, context) -> None:
        stmts = self._statements()
        self.log.info("ClickHouseOperator running %s statement(s)", len(stmts))
        for i, stmt in enumerate(stmts, 1):
            self.log.info("[%s/%s] %s", i, len(stmts), stmt.split("\n")[0][:120])
            clients.ch_execute(stmt, timeout=self.timeout)
