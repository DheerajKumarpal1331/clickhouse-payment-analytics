"""Materialize the ONLINE store: run each group's online SQL so
online_features holds the latest feature vector per entity (ReplacingMergeTree).
"""
from __future__ import annotations

import time

import clickhouse_client as ch
from config import CH_DB
from definitions import REGISTRY


def run() -> dict[str, float]:
    """Refresh all online feature groups. Returns {entity: seconds}."""
    timings: dict[str, float] = {}
    for g in REGISTRY:
        t0 = time.time()
        ch.execute(g.online_sql(CH_DB))
        timings[g.entity] = round(time.time() - t0, 3)
    return timings


if __name__ == "__main__":
    print("online materialize:", run())
