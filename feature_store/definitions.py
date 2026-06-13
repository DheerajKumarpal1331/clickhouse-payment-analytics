"""Feature registry — the single declaration of every feature group, its
entity, the features it produces, and the SQL that materializes the online and
offline stores. Materializers and tests iterate this; nothing else hard-codes
the feature list.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from pipelines import merchant_features, customer_features, device_features
import config


@dataclass(frozen=True)
class FeatureGroup:
    entity: str
    features: list[str]
    online_sql: Callable[[str], str]    # (db) -> INSERT ... online_features
    offline_sql: Callable[[str], str]   # (db) -> INSERT ... offline_features


REGISTRY: list[FeatureGroup] = [
    FeatureGroup(
        entity=merchant_features.ENTITY,
        features=merchant_features.FEATURES,
        online_sql=lambda db: merchant_features.online_sql(db, config.RATE_WINDOW_DAYS),
        offline_sql=lambda db: merchant_features.offline_sql(db, config.OFFLINE_BACKFILL_DAYS, config.FEATURE_SET),
    ),
    FeatureGroup(
        entity=customer_features.ENTITY,
        features=customer_features.FEATURES,
        online_sql=lambda db: customer_features.online_sql(db, config.RATE_WINDOW_DAYS, config.SPEND_WINDOW_DAYS),
        offline_sql=lambda db: customer_features.offline_sql(db, config.OFFLINE_BACKFILL_DAYS, config.FEATURE_SET),
    ),
    FeatureGroup(
        entity=device_features.ENTITY,
        features=device_features.FEATURES,
        online_sql=lambda db: device_features.online_sql(db),
        offline_sql=lambda db: device_features.offline_sql(db, config.OFFLINE_BACKFILL_DAYS, config.FEATURE_SET),
    ),
]

GROUPS = {g.entity: g for g in REGISTRY}
ALL_FEATURES = {g.entity: g.features for g in REGISTRY}
