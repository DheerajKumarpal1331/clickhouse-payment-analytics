"""Online feature serving — the read path used by the fraud scoring API.
Single-key lookup against online_features (ReplacingMergeTree, FINAL) returns
the latest feature vector for an entity in ~1ms.
"""
from __future__ import annotations

import clickhouse_client as ch
from config import CH_DB


def _esc(s: str) -> str:
    return s.replace("'", "\\'")


def get_online_features(entity_type: str, entity_id: str,
                        feature_names: list[str] | None = None) -> dict[str, float]:
    """Latest features for one entity. Empty dict if the entity is unknown."""
    rows = ch.query(f"""
        SELECT features FROM {CH_DB}.online_features FINAL
        WHERE entity_type = '{_esc(entity_type)}' AND entity_id = '{_esc(entity_id)}'
        LIMIT 1
    """)
    if not rows:
        return {}
    feats = rows[0].get("features", {})
    if feature_names:
        return {k: float(feats.get(k, 0.0)) for k in feature_names}
    return {k: float(v) for k, v in feats.items()}


def get_many(entity_type: str, entity_ids: list[str]) -> dict[str, dict[str, float]]:
    """Batch lookup for several entities of one type (one round-trip)."""
    if not entity_ids:
        return {}
    ids = ",".join(f"'{_esc(e)}'" for e in entity_ids)
    rows = ch.query(f"""
        SELECT entity_id, features FROM {CH_DB}.online_features FINAL
        WHERE entity_type = '{_esc(entity_type)}' AND entity_id IN ({ids})
    """)
    return {r["entity_id"]: {k: float(v) for k, v in r["features"].items()} for r in rows}


if __name__ == "__main__":
    import sys
    et, eid = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("merchant", "")
    print(get_online_features(et, eid))
