"""Feature store (Phase 6): computes merchant/customer/device features in
ClickHouse and serves them online (latest, ReplacingMergeTree) for the fraud
API and offline (point-in-time, ASOF-joined) for model training."""
