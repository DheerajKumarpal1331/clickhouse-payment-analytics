"""Assert SQL-metric expectations against ClickHouse (or Postgres) and fail the
task — and so page the on-call DAG — when a contract is breached.

Each check is a ``Check(name, sql, ...)`` whose ``sql`` returns a single number;
the value is compared against the configured bound(s). A failing check raises
``AirflowFailException`` (no retry — a data contract breach won't fix itself on
re-run) and the full pass/fail table is logged and pushed to XCom.

Supported bounds (any combination): ``min_value``, ``max_value``,
``equals``, ``warn_only`` (logs a WARNING instead of failing).
"""
from __future__ import annotations

from dataclasses import dataclass

from airflow.exceptions import AirflowFailException
from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults

from operators import clients


@dataclass
class Check:
    name: str
    sql: str
    min_value: float | None = None
    max_value: float | None = None
    equals: float | None = None
    warn_only: bool = False
    source: str = "clickhouse"           # "clickhouse" | "postgres"

    def evaluate(self, value: float) -> str | None:
        """Return None if the check passes, else a failure reason."""
        if self.equals is not None and value != self.equals:
            return f"expected == {self.equals}, got {value}"
        if self.min_value is not None and value < self.min_value:
            return f"expected >= {self.min_value}, got {value}"
        if self.max_value is not None and value > self.max_value:
            return f"expected <= {self.max_value}, got {value}"
        return None


class DataQualityOperator(BaseOperator):
    ui_color = "#e53e3e"

    @apply_defaults
    def __init__(self, checks: list[Check], **kwargs):
        super().__init__(**kwargs)
        self.checks = checks

    def _value(self, check: Check) -> float:
        if check.source == "postgres":
            rows = clients.pg_fetch(check.sql)
            v = next(iter(rows[0].values())) if rows else 0
        else:
            v = clients.ch_scalar(check.sql)
        return float(v if v is not None else 0)

    def execute(self, context) -> dict:
        results, failures = {}, []
        for check in self.checks:
            value = self._value(check)
            reason = check.evaluate(value)
            status = "PASS" if reason is None else ("WARN" if check.warn_only else "FAIL")
            results[check.name] = {"value": value, "status": status, "reason": reason}
            self.log.info("[%s] %s = %s%s", status, check.name, value,
                          f"  ({reason})" if reason else "")
            if reason and not check.warn_only:
                failures.append(f"{check.name}: {reason}")

        context["ti"].xcom_push(key="dq_results", value=results)
        if failures:
            raise AirflowFailException("Data quality failed -> " + "; ".join(failures))
        return results
