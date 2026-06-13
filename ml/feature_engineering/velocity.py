"""Velocity feature engineering — the heart of fraud detection.

Computes, per transaction, the behavioural velocity features that separate
fraud bursts from normal activity, using ClickHouse window functions with
time-RANGE frames (numeric unix-second offsets) and lagInFrame for geo speed:

  cust_velocity_5m/1h/24h : the customer's txn count in the trailing window
  device_velocity_1h      : the device's txn count in the trailing hour
  merchant_velocity_1h    : the merchant's txn count in the trailing hour
  geo_velocity_kmph       : great-circle distance from the customer's previous
                            txn / elapsed hours (impossible-travel signal)

count() OVER (... RANGE BETWEEN N PRECEDING AND CURRENT ROW) gives true rolling
time windows; the current row is included (so velocity >= 1).
"""
from __future__ import annotations

from ml.config import CH_DB


def training_sql(sample: int, db: str = CH_DB) -> str:
    """Labeled per-transaction feature matrix for training/eval. Sampled and
    ordered by time so the caller can do a leakage-free time split."""
    return f"""
WITH base AS (
    SELECT
        transaction_id, customer_id, device_id, merchant_id,
        fraud_label,
        toFloat64(amount) AS amount,
        toUInt8(is_international) AS is_international,
        toUnixTimestamp(event_time) AS ts,
        event_time, latitude, longitude
    FROM {db}.fact_transactions
    WHERE customer_id != ''
)
SELECT
    fraud_label AS label,
    toUnixTimestamp(event_time) AS ts,
    amount,
    is_international,
    count() OVER (PARTITION BY customer_id ORDER BY ts RANGE BETWEEN 300 PRECEDING AND CURRENT ROW)   AS cust_velocity_5m,
    count() OVER (PARTITION BY customer_id ORDER BY ts RANGE BETWEEN 3600 PRECEDING AND CURRENT ROW)  AS cust_velocity_1h,
    count() OVER (PARTITION BY customer_id ORDER BY ts RANGE BETWEEN 86400 PRECEDING AND CURRENT ROW) AS cust_velocity_24h,
    count() OVER (PARTITION BY device_id   ORDER BY ts RANGE BETWEEN 3600 PRECEDING AND CURRENT ROW)  AS device_velocity_1h,
    count() OVER (PARTITION BY merchant_id ORDER BY ts RANGE BETWEEN 3600 PRECEDING AND CURRENT ROW)  AS merchant_velocity_1h,
    greatCircleDistance(
        lagInFrame(longitude) OVER w_cust, lagInFrame(latitude) OVER w_cust,
        longitude, latitude
    ) / 1000.0
      / greatest((ts - lagInFrame(ts) OVER w_cust) / 3600.0, 1.0 / 60.0) AS geo_velocity_kmph
FROM base
WINDOW w_cust AS (PARTITION BY customer_id ORDER BY ts)
ORDER BY ts
LIMIT {sample}
"""

# At serving time the same features are read from the feature store
# (feature_store.online.get_online_features + clickhouse v_velocity_1h),
# not recomputed here — training and serving share one definition.
