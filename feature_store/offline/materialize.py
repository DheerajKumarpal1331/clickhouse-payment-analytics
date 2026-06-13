"""Materialize the OFFLINE store: run each group's offline SQL to append daily
point-in-time snapshots into offline_features. Run on a schedule (Airflow) so a
true feature history accumulates for leakage-free training.
"""
from __future__ import annotations

import time

import clickhouse_client as ch
from config import CH_DB
from definitions import REGISTRY


def run() -> dict[str, float]:
    timings: dict[str, float] = {}
    for g in REGISTRY:
        t0 = time.time()
        ch.execute(g.offline_sql(CH_DB))
        timings[g.entity] = round(time.time() - t0, 3)
    return timings


if __name__ == "__main__":
    print("offline materialize:", run())
