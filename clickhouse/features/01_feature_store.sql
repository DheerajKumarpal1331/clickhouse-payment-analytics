-- ============================================================
-- Feature store tables (Phase 5 — consumed by the ML phase).
--   offline_features : append-only, point-in-time correct. Training joins use
--                      ASOF JOIN ... feature_time <= label_time (no leakage).
--   online_features  : latest-per-entity (ReplacingMergeTree), single-key read
--                      by the fraud API in <1ms.
-- ============================================================
CREATE TABLE IF NOT EXISTS payments.offline_features
(
    entity_type  LowCardinality(String),     -- merchant | customer | device | card
    entity_id    String,
    feature_time DateTime,
    feature_set  LowCardinality(String),     -- e.g. 'fraud_v2'
    features     Map(LowCardinality(String), Float64),
    computed_at  DateTime DEFAULT now()
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(feature_time)
ORDER BY (entity_type, entity_id, feature_time);

CREATE TABLE IF NOT EXISTS payments.online_features
(
    entity_type LowCardinality(String),
    entity_id   String,
    features    Map(LowCardinality(String), Float64),
    updated_at  DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (entity_type, entity_id)
TTL updated_at + INTERVAL 30 DAY;
