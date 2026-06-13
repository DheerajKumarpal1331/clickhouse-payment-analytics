"""Customer feature pipeline.

avg_ticket_size       : mean transaction amount over the spend window (90d)
transaction_frequency : txns over the rate window (30d)
merchant_diversity    : distinct merchants paid over the spend window
"""
from __future__ import annotations

ENTITY = "customer"
FEATURES = ["avg_ticket_size", "transaction_frequency", "merchant_diversity"]


def online_sql(db: str, rate_days: int, spend_days: int) -> str:
    return f"""
INSERT INTO {db}.online_features (entity_type, entity_id, features)
SELECT 'customer' AS entity_type,
       customer_id AS entity_id,
       map(
         'avg_ticket_size',       avg(toFloat64(amount)),
         'transaction_frequency', toFloat64(countIf(event_time >= now() - INTERVAL {rate_days} DAY)),
         'merchant_diversity',    toFloat64(uniq(merchant_id))
       ) AS features
FROM {db}.fact_transactions
WHERE customer_id != '' AND event_time >= now() - INTERVAL {spend_days} DAY
GROUP BY customer_id
"""


def offline_sql(db: str, backfill_days: int, feature_set: str) -> str:
    return f"""
INSERT INTO {db}.offline_features (entity_type, entity_id, feature_time, feature_set, features)
SELECT 'customer' AS entity_type,
       customer_id AS entity_id,
       toDateTime(toDate(event_time)) AS feature_time,
       '{feature_set}' AS feature_set,
       map(
         'avg_ticket_size',       avg(toFloat64(amount)),
         'transaction_frequency', toFloat64(count()),
         'merchant_diversity',    toFloat64(uniq(merchant_id))
       ) AS features
FROM {db}.fact_transactions
WHERE customer_id != '' AND event_time >= today() - {backfill_days}
GROUP BY customer_id, toDate(event_time)
"""
