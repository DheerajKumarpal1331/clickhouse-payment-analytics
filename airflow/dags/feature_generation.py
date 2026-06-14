"""feature_generation — refresh the ClickHouse feature store (Phase 6) on a
schedule: the current per-merchant snapshot for online serving, and the daily
point-in-time rows for leakage-free training sets.

Velocity features (customer/device/merchant 5m–24h) are kept fresh by ClickHouse
materialized views on insert, so this DAG only needs to (1) recompute the online
snapshot, (2) append today's offline PIT rows, and (3) collapse the
ReplacingMergeTree online table so serving reads one row per entity.

The INSERT…SELECT statements are the canonical merchant pipeline from
feature_store/pipelines/merchant_features.py, embedded so the Airflow deployment
stays self-contained. Hourly; gated on transactions having landed for the day.
"""
from __future__ import annotations

from airflow import DAG

from common import DB, DEFAULT_ARGS, START, TAGS
from operators import ClickHouseOperator
from sensors import ClickHousePartitionSensor

RATE_DAYS = 30
BACKFILL_DAYS = 1          # the offline DAG run appends only the latest day(s)
FEATURE_SET = "merchant_v1"

ONLINE_MERCHANT_SQL = f"""
INSERT INTO {DB}.online_features (entity_type, entity_id, features)
SELECT 'merchant' AS entity_type,
       t.merchant_id AS entity_id,
       map(
         'transaction_velocity', toFloat64(t.txns_1h),
         'success_rate',    if(t.txns_w > 0, t.success_w / t.txns_w, 0),
         'refund_rate',     if(t.txns_w > 0, r.refunds_w / t.txns_w, 0),
         'chargeback_ratio',if(t.txns_w > 0, c.cbs_w / t.txns_w, 0)
       ) AS features
FROM (
    SELECT merchant_id,
           countIf(event_time >= now() - INTERVAL 1 HOUR) AS txns_1h,
           count()                                        AS txns_w,
           sumIf(is_success, is_success = 1)              AS success_w
    FROM {DB}.fact_transactions
    WHERE event_time >= now() - INTERVAL {RATE_DAYS} DAY
    GROUP BY merchant_id
) AS t
LEFT JOIN (
    SELECT merchant_id, count() AS refunds_w FROM {DB}.fact_refunds
    WHERE event_time >= now() - INTERVAL {RATE_DAYS} DAY GROUP BY merchant_id
) AS r ON r.merchant_id = t.merchant_id
LEFT JOIN (
    SELECT merchant_id, count() AS cbs_w FROM {DB}.fact_chargebacks
    WHERE event_time >= now() - INTERVAL {RATE_DAYS} DAY GROUP BY merchant_id
) AS c ON c.merchant_id = t.merchant_id
"""

OFFLINE_MERCHANT_SQL = f"""
INSERT INTO {DB}.offline_features (entity_type, entity_id, feature_time, feature_set, features)
SELECT 'merchant' AS entity_type,
       d.merchant_id AS entity_id,
       toDateTime(d.event_date) AS feature_time,
       '{FEATURE_SET}' AS feature_set,
       map(
         'transaction_velocity', toFloat64(d.txns),
         'success_rate',    d.success_rate,
         'refund_rate',     if(d.txns > 0, rf.refunds / d.txns, 0),
         'chargeback_ratio',if(d.txns > 0, cb.cbs / d.txns, 0)
       ) AS features
FROM {DB}.merchant_daily_summary AS d
LEFT JOIN (
    SELECT merchant_id, toDate(event_time) AS dt, count() AS refunds
    FROM {DB}.fact_refunds WHERE event_time >= today() - {BACKFILL_DAYS}
    GROUP BY merchant_id, dt
) AS rf ON rf.merchant_id = d.merchant_id AND rf.dt = d.event_date
LEFT JOIN (
    SELECT merchant_id, toDate(event_time) AS dt, count() AS cbs
    FROM {DB}.fact_chargebacks WHERE event_time >= today() - {BACKFILL_DAYS}
    GROUP BY merchant_id, dt
) AS cb ON cb.merchant_id = d.merchant_id AND cb.dt = d.event_date
WHERE d.event_date >= today() - {BACKFILL_DAYS}
"""

with DAG(
    dag_id="feature_generation",
    description="Refresh online + offline feature store (Phase 6)",
    default_args=DEFAULT_ARGS,
    schedule="@hourly",
    start_date=START,
    catchup=False,
    max_active_runs=1,
    tags=TAGS + ["features"],
) as dag:

    wait = ClickHousePartitionSensor(
        task_id="wait_for_todays_transactions",
        table=f"{DB}.fact_transactions",
        date_column="event_date",
        min_rows=1,
        mode="reschedule",
        poke_interval=300,
        timeout=1800,
        soft_fail=True,
    )

    online = ClickHouseOperator(task_id="materialize_online_features", sql=ONLINE_MERCHANT_SQL)
    offline = ClickHouseOperator(task_id="materialize_offline_features", sql=OFFLINE_MERCHANT_SQL)
    compact = ClickHouseOperator(
        task_id="compact_online_features",
        sql=f"OPTIMIZE TABLE {DB}.online_features FINAL",
    )

    wait >> online >> offline >> compact
