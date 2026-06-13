"""Device feature pipeline.

device_velocity  : txns in the last hour (burst signal for takeover/velocity fraud)
location_changes : distinct cities seen in the last 24h (impossible-travel signal)
failure_rate     : declined / total over the last 7 days (faulty/abused terminal)
"""
from __future__ import annotations

ENTITY = "device"
FEATURES = ["device_velocity", "location_changes", "failure_rate"]


def online_sql(db: str) -> str:
    return f"""
INSERT INTO {db}.online_features (entity_type, entity_id, features)
SELECT 'device' AS entity_type,
       device_id AS entity_id,
       map(
         'device_velocity',  toFloat64(countIf(event_time >= now() - INTERVAL 1 HOUR)),
         'location_changes', toFloat64(uniqIf(city, event_time >= now() - INTERVAL 24 HOUR)),
         'failure_rate',     if(count() > 0, countIf(is_success = 0) / count(), 0)
       ) AS features
FROM {db}.fact_transactions
WHERE device_id != '' AND event_time >= now() - INTERVAL 7 DAY
GROUP BY device_id
"""


def offline_sql(db: str, backfill_days: int, feature_set: str) -> str:
    return f"""
INSERT INTO {db}.offline_features (entity_type, entity_id, feature_time, feature_set, features)
SELECT 'device' AS entity_type,
       device_id AS entity_id,
       toDateTime(toDate(event_time)) AS feature_time,
       '{feature_set}' AS feature_set,
       map(
         'device_velocity',  toFloat64(count()),
         'location_changes', toFloat64(uniq(city)),
         'failure_rate',     if(count() > 0, countIf(is_success = 0) / count(), 0)
       ) AS features
FROM {db}.fact_transactions
WHERE device_id != '' AND event_time >= today() - {backfill_days}
GROUP BY device_id, toDate(event_time)
"""
