"""refund_ingestion — CDC of refund requests (refund.refund_requests) into
ClickHouse fact_refunds.

Refunds feed merchant refund-rate features and the settlement net calculation,
so they are loaded on a tight cadence (every 10 minutes) off the
``requested_at`` cursor.
"""
from __future__ import annotations

from airflow import DAG

from common import DEFAULT_ARGS, START, TAGS
from operators import PostgresToClickHouseOperator
from sensors import PostgresRowSensor

with DAG(
    dag_id="refund_ingestion",
    description="CDC refund.refund_requests -> payments.fact_refunds",
    default_args=DEFAULT_ARGS,
    schedule="*/10 * * * *",
    start_date=START,
    catchup=False,
    max_active_runs=1,
    tags=TAGS + ["ingestion", "refunds"],
) as dag:

    wait = PostgresRowSensor(
        task_id="wait_for_new_refunds",
        source="refund",
        mode="reschedule",
        poke_interval=90,
        timeout=300,
        soft_fail=True,
    )

    load = PostgresToClickHouseOperator(
        task_id="load_refunds",
        source="refund",
        batch_size=20_000,
    )

    wait >> load
