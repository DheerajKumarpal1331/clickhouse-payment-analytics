"""Merchant feature pipeline.

transaction_velocity : txns in the last hour (recent throughput)
success_rate         : approved / total over the rate window (30d)
refund_rate          : refunds / txns over the window
chargeback_ratio     : chargebacks / txns over the window  (the risk red-flag)

Both queries compute server-side in ClickHouse and write a Map of features.
"""
from __future__ import annotations

ENTITY = "merchant"
FEATURES = ["transaction_velocity", "success_rate", "refund_rate", "chargeback_ratio"]


def online_sql(db: str, rate_days: int) -> str:
    """Current snapshot per merchant -> online_features (latest)."""
    return f"""
INSERT INTO {db}.online_features (entity_type, entity_id, features)
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
           countIf(event_time >= now() - INTERVAL 1 HOUR)          AS txns_1h,
           count()                                                  AS txns_w,
           sumIf(is_success, is_success = 1)                        AS success_w
    FROM {db}.fact_transactions
    WHERE event_time >= now() - INTERVAL {rate_days} DAY
    GROUP BY merchant_id
) AS t
LEFT JOIN (
    SELECT merchant_id, count() AS refunds_w FROM {db}.fact_refunds
    WHERE event_time >= now() - INTERVAL {rate_days} DAY GROUP BY merchant_id
) AS r ON r.merchant_id = t.merchant_id
LEFT JOIN (
    SELECT merchant_id, count() AS cbs_w FROM {db}.fact_chargebacks
    WHERE event_time >= now() - INTERVAL {rate_days} DAY GROUP BY merchant_id
) AS c ON c.merchant_id = t.merchant_id
"""


def offline_sql(db: str, backfill_days: int, feature_set: str) -> str:
    """Daily point-in-time snapshots -> offline_features (time series)."""
    return f"""
INSERT INTO {db}.offline_features (entity_type, entity_id, feature_time, feature_set, features)
SELECT 'merchant' AS entity_type,
       d.merchant_id AS entity_id,
       toDateTime(d.event_date) AS feature_time,
       '{feature_set}' AS feature_set,
       map(
         'transaction_velocity', toFloat64(d.txns),
         'success_rate',    d.success_rate,
         'refund_rate',     if(d.txns > 0, rf.refunds / d.txns, 0),
         'chargeback_ratio',if(d.txns > 0, cb.cbs / d.txns, 0)
       ) AS features
FROM {db}.merchant_daily_summary AS d
LEFT JOIN (
    SELECT merchant_id, toDate(event_time) AS dt, count() AS refunds
    FROM {db}.fact_refunds WHERE event_time >= today() - {backfill_days}
    GROUP BY merchant_id, dt
) AS rf ON rf.merchant_id = d.merchant_id AND rf.dt = d.event_date
LEFT JOIN (
    SELECT merchant_id, toDate(event_time) AS dt, count() AS cbs
    FROM {db}.fact_chargebacks WHERE event_time >= today() - {backfill_days}
    GROUP BY merchant_id, dt
) AS cb ON cb.merchant_id = d.merchant_id AND cb.dt = d.event_date
WHERE d.event_date >= today() - {backfill_days}
"""
