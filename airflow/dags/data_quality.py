"""data_quality — contract checks across the warehouse and a source-freshness
check against the OLTP. A breach fails the task (no retry) so it surfaces in the
UI / Alertmanager; soft expectations are flagged ``warn_only`` so they log a
WARNING without paging.

Checks asserted hourly:
  • volume          — fact_transactions is non-empty
  • completeness    — no blank merchant_id on transactions (key integrity)
  • validity        — fraud_label rate is plausibly in [0, 0.2]
  • consistency     — no settlement where net_amount > gross_amount
  • dedupe          — fact_transactions distinct ratio ~1 (warn) — pre-merge dupes
  • freshness (PG)  — newest OLTP transaction is within the last 24h
"""
from __future__ import annotations

from airflow import DAG

from common import DB, DEFAULT_ARGS, START, TAGS
from operators import DataQualityOperator
from operators.data_quality_operator import Check

CHECKS = [
    Check(
        name="transactions_volume",
        sql=f"SELECT count() FROM {DB}.fact_transactions",
        min_value=1,
    ),
    Check(
        name="transactions_merchant_id_complete",
        sql=f"SELECT countIf(merchant_id = '') FROM {DB}.fact_transactions",
        equals=0,
    ),
    Check(
        name="fraud_rate_plausible",
        sql=f"SELECT avg(fraud_label) FROM {DB}.fact_transactions",
        min_value=0.0, max_value=0.2,
    ),
    Check(
        name="settlement_net_not_above_gross",
        sql=f"SELECT countIf(net_amount > gross_amount) FROM {DB}.fact_settlements",
        equals=0,
    ),
    Check(
        name="transactions_distinct_ratio",
        sql=(f"SELECT if(count() = 0, 1, uniqExact(transaction_id) / count()) "
             f"FROM {DB}.fact_transactions"),
        min_value=0.98, warn_only=True,     # ReplacingMergeTree dedupe is at read time
    ),
    Check(
        name="oltp_transaction_freshness_24h",
        source="postgres",
        sql=("SELECT EXTRACT(EPOCH FROM (now() - max(created_at))) / 3600.0 "
             "FROM txn.transaction_header"),
        max_value=24.0, warn_only=True,     # warns in dev where the stream is idle
    ),
]

with DAG(
    dag_id="data_quality",
    description="Warehouse data-quality contracts + OLTP source freshness",
    default_args=DEFAULT_ARGS,
    schedule="@hourly",
    start_date=START,
    catchup=False,
    max_active_runs=1,
    tags=TAGS + ["data-quality", "observability"],
) as dag:

    DataQualityOperator(task_id="run_quality_checks", checks=CHECKS)
