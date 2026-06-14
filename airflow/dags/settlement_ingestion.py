"""settlement_ingestion — CDC of per-merchant settlement records
(settlement.merchant_settlements ⨝ settlement_batches) into fact_settlements.

Settlement batches are built by the OLTP T+1 job, so this DAG runs hourly to
pick up newly cut batches off the ``created_at`` cursor and joins the batch's
cycle_date for the warehouse partition key. Feeds the settlement-ops mart and
the settlement-TAT dashboard.
"""
from __future__ import annotations

from airflow import DAG

from common import DEFAULT_ARGS, START, TAGS
from operators import PostgresToClickHouseOperator
from sensors import PostgresRowSensor

with DAG(
    dag_id="settlement_ingestion",
    description="CDC settlement.merchant_settlements -> payments.fact_settlements",
    default_args=DEFAULT_ARGS,
    schedule="@hourly",
    start_date=START,
    catchup=False,
    max_active_runs=1,
    tags=TAGS + ["ingestion", "settlement"],
) as dag:

    wait = PostgresRowSensor(
        task_id="wait_for_new_settlements",
        source="settlement",
        mode="reschedule",
        poke_interval=300,
        timeout=900,
        soft_fail=True,
    )

    load = PostgresToClickHouseOperator(
        task_id="load_settlements",
        source="settlement",
        batch_size=20_000,
    )

    wait >> load
