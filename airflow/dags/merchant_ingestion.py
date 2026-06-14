"""merchant_ingestion — CDC of the merchant master (merchant.merchant_master)
into the ClickHouse dimension payments.dim_merchants.

dim_merchants is a ReplacingMergeTree keyed on (merchant_id) versioned by
updated_at, so re-loading a changed merchant simply supersedes the old row on
merge. The cursor follows ``updated_at`` so onboarding edits and status changes
flow through. Runs every 15 minutes — dimensions change far less often than the
transaction stream.
"""
from __future__ import annotations

from airflow import DAG

from common import DEFAULT_ARGS, START, TAGS
from operators import PostgresToClickHouseOperator
from sensors import PostgresRowSensor

with DAG(
    dag_id="merchant_ingestion",
    description="CDC merchant.merchant_master -> payments.dim_merchants (SCD via ReplacingMergeTree)",
    default_args=DEFAULT_ARGS,
    schedule="*/15 * * * *",
    start_date=START,
    catchup=False,
    max_active_runs=1,
    tags=TAGS + ["ingestion", "dimensions"],
) as dag:

    wait = PostgresRowSensor(
        task_id="wait_for_merchant_changes",
        source="merchant",
        mode="reschedule",
        poke_interval=120,
        timeout=300,
        soft_fail=True,
    )

    load = PostgresToClickHouseOperator(
        task_id="load_merchants",
        source="merchant",
        batch_size=10_000,
    )

    wait >> load
