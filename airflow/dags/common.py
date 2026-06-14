"""Shared DAG defaults and the warehouse database name.

Kept tiny and import-safe (no store connections at parse time) so the scheduler
can parse every DAG cheaply. ``DB`` is the ClickHouse database all facts /
features / marts live in (Phase 5).
"""
from __future__ import annotations

from datetime import timedelta

import pendulum

DB = "payments"
TZ = pendulum.timezone("Asia/Kolkata")          # IST — the platform's home market
START = pendulum.datetime(2024, 1, 1, tz="Asia/Kolkata")   # shared DAG start_date

DEFAULT_ARGS = {
    "owner": "data-platform",
    "retries": 2,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=15),
    "depends_on_past": False,
    "email_on_failure": False,        # alerting wired via on_failure_callback / Alertmanager
}

# Common tags so the UI groups the platform's DAGs together.
TAGS = ["payments"]
