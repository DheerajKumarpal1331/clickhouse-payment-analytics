"""transaction_ingestion — micro-batch CDC of authorizations from the OLTP
switch (txn.transaction_header) into ClickHouse fact_transactions.

This is the scheduled, gap-filling complement to the Kafka streaming path: even
if the streaming consumer is down, this DAG keeps the warehouse converged from
the durable ``(wm, id)`` cursor. Runs every 5 minutes; the sensor short-circuits
an empty run, ``max_active_runs=1`` keeps the cursor single-writer.
"""
from __future__ import annotations

from airflow import DAG

from common import DEFAULT_ARGS, START, TAGS
from operators import PostgresToClickHouseOperator
from sensors import PostgresRowSensor

with DAG(
    dag_id="transaction_ingestion",
    description="CDC txn.transaction_header -> payments.fact_transactions",
    default_args=DEFAULT_ARGS,
    schedule="*/5 * * * *",
    start_date=START,
    catchup=False,
    max_active_runs=1,
    tags=TAGS + ["ingestion", "transactions"],
) as dag:

    wait = PostgresRowSensor(
        task_id="wait_for_new_transactions",
        source="transaction",
        mode="reschedule",          # free the worker slot while polling
        poke_interval=60,
        timeout=240,
        soft_fail=True,             # no new rows in the window -> skip, don't fail
    )

    load = PostgresToClickHouseOperator(
        task_id="load_transactions",
        source="transaction",
        batch_size=50_000,
    )

    wait >> load
