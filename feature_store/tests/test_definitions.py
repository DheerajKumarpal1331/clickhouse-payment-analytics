"""Registry + SQL-shape tests (no infra). Run:
    python feature_store/tests/test_definitions.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from definitions import REGISTRY, GROUPS, ALL_FEATURES  # noqa: E402

EXPECTED = {
    "merchant": {"transaction_velocity", "success_rate", "refund_rate", "chargeback_ratio"},
    "customer": {"avg_ticket_size", "transaction_frequency", "merchant_diversity"},
    "device":   {"device_velocity", "location_changes", "failure_rate"},
}


def test_three_entity_groups():
    assert set(GROUPS) == {"merchant", "customer", "device"}


def test_features_match_spec():
    for entity, feats in EXPECTED.items():
        assert set(ALL_FEATURES[entity]) == feats, entity


def test_sql_builders_emit_inserts():
    for g in REGISTRY:
        on, off = g.online_sql("payments"), g.offline_sql("payments")
        assert "INSERT INTO payments.online_features" in on
        assert "INSERT INTO payments.offline_features" in off
        # every declared feature appears as a map key in both queries
        for f in g.features:
            assert f"'{f}'" in on and f"'{f}'" in off, (g.entity, f)


def test_offline_is_point_in_time():
    # offline must carry feature_time + feature_set (PIT history)
    for g in REGISTRY:
        off = g.offline_sql("payments")
        assert "feature_time" in off and "feature_set" in off


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} feature-store tests passed")
