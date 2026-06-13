"""Point-in-time correct training-set assembly.

The cardinal rule of fraud ML: a training row's features must reflect only what
was known *before* the label time. We enforce that with an ASOF LEFT JOIN on
offline_features (feature_time <= label_time), picking the most recent snapshot
per entity. This is the leakage guard the LLD calls out.
"""
from __future__ import annotations

import clickhouse_client as ch
from config import CH_DB


def _esc(s: str) -> str:
    return s.replace("'", "\\'")


def point_in_time(entity_type: str, entity_id: str, as_of: str,
                  feature_set: str = "fraud_v1") -> dict[str, float]:
    """Features for one entity as they were known at `as_of` ('YYYY-MM-DD HH:MM:SS')."""
    rows = ch.query(f"""
        SELECT features FROM {CH_DB}.offline_features
        WHERE entity_type = '{_esc(entity_type)}' AND entity_id = '{_esc(entity_id)}'
          AND feature_set = '{_esc(feature_set)}' AND feature_time <= toDateTime('{_esc(as_of)}')
        ORDER BY feature_time DESC LIMIT 1
    """)
    return {k: float(v) for k, v in rows[0]["features"].items()} if rows else {}


def build_training_set(entity_type: str, labels_table: str,
                       feature_set: str = "fraud_v1") -> str:
    """Return the ASOF-join SQL that materializes a leakage-free training matrix.

    `labels_table` must have columns (entity_id String, label_time DateTime,
    label UInt8). Caller can wrap this in INSERT INTO ... or run it directly.
    """
    return f"""
SELECT l.entity_id,
       l.label_time,
       l.label,
       f.features
FROM {labels_table} AS l
ASOF LEFT JOIN
(
    SELECT entity_id, feature_time, features
    FROM {CH_DB}.offline_features
    WHERE entity_type = '{_esc(entity_type)}' AND feature_set = '{_esc(feature_set)}'
) AS f
  ON f.entity_id = l.entity_id AND f.feature_time <= l.label_time
"""


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 3:
        print(point_in_time(sys.argv[1], sys.argv[2], sys.argv[3]))
