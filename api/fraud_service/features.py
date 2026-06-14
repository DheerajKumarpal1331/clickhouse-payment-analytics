"""Real-time velocity feature assembly for scoring. Reads the same signals the
model trained on, but for the *incoming* transaction's entities — a few indexed
ClickHouse lookups against the velocity store (agg_velocity_5m), the merchant
hourly rollup, and the customer's last transaction (geo speed). Sub-100ms.

The transaction being scored is NOT yet in the store, so velocity reflects
prior activity — exactly what pre-authorization scoring needs.
"""
from __future__ import annotations

import time

from api.common import clickhouse as ch
from api.common.config import CH_DB
from ml.config import FEATURE_COLUMNS

DB = CH_DB


def _esc(s: str) -> str:
    return (s or "").replace("'", "\\'")


def assemble(merchant_id: str, customer_id: str, device_id: str,
             amount: float, is_international: int,
             latitude: float = 0.0, longitude: float = 0.0) -> dict:
    feats = {c: 0.0 for c in FEATURE_COLUMNS}
    feats["amount"] = float(amount)
    feats["is_international"] = float(int(is_international))
    now = time.time()

    # Customer velocity: pull last-24h buckets once, fold into 5m/1h/24h.
    if customer_id:
        rows = ch.query(f"""
            SELECT toUnixTimestamp(bucket) AS b, countMerge(txn_count) AS c
            FROM {DB}.agg_velocity_5m
            WHERE entity_type='customer' AND entity_id='{_esc(customer_id)}'
              AND bucket >= now() - INTERVAL 24 HOUR
            GROUP BY bucket
        """)
        for r in rows:
            age = now - float(r["b"]); c = float(r["c"])
            if age <= 300:    feats["cust_velocity_5m"] += c
            if age <= 3600:   feats["cust_velocity_1h"] += c
            if age <= 86400:  feats["cust_velocity_24h"] += c

        geo = ch.query_one(f"""
            SELECT greatCircleDistance(longitude, latitude, {float(longitude)}, {float(latitude)}) / 1000.0
                   / greatest(dateDiff('second', event_time, now()) / 3600.0, 1.0/60) AS v
            FROM {DB}.fact_transactions
            WHERE customer_id='{_esc(customer_id)}' ORDER BY event_time DESC LIMIT 1
        """)
        feats["geo_velocity_kmph"] = float(geo.get("v", 0) or 0)

    if device_id:
        d = ch.query_one(f"""
            SELECT countMerge(txn_count) AS c FROM {DB}.agg_velocity_5m
            WHERE entity_type='device' AND entity_id='{_esc(device_id)}'
              AND bucket >= now() - INTERVAL 1 HOUR
        """)
        feats["device_velocity_1h"] = float(d.get("c", 0) or 0)

    if merchant_id:
        m = ch.query_one(f"""
            SELECT countMerge(txn_count) AS c FROM {DB}.agg_merchant_hourly
            WHERE merchant_id='{_esc(merchant_id)}' AND event_hour >= now() - INTERVAL 1 HOUR
        """)
        feats["merchant_velocity_1h"] = float(m.get("c", 0) or 0)

    return feats
