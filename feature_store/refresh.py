"""Feature store refresher — the container entrypoint.

    python -m feature_store.refresh --once            # one online+offline pass
    python -m feature_store.refresh --loop            # continuous (container default)
    python -m feature_store.refresh --once --mode online

In --loop it exposes Prometheus metrics on METRICS_PORT (/metrics), scraped by
the platform's Prometheus (job: services / feature-store).
"""
from __future__ import annotations

import argparse
import time

from config import METRICS_PORT, REFRESH_INTERVAL_SEC
from online import materialize as online_mat
from offline import materialize as offline_mat

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
    _PROM = True
except ImportError:                       # metrics optional for local --once
    _PROM = False

if _PROM:
    REFRESHES = Counter("fs_refreshes_total", "Feature refresh passes", ["mode"])
    LAST_TS = Gauge("fs_last_refresh_timestamp", "Unix ts of last refresh", ["mode"])
    DURATION = Histogram("fs_refresh_duration_seconds", "Refresh duration", ["mode", "entity"])


def _pass(mode: str) -> None:
    if mode in ("online", "both"):
        for entity, secs in online_mat.run().items():
            if _PROM:
                DURATION.labels("online", entity).observe(secs)
        if _PROM:
            REFRESHES.labels("online").inc(); LAST_TS.labels("online").set(time.time())
    if mode in ("offline", "both"):
        for entity, secs in offline_mat.run().items():
            if _PROM:
                DURATION.labels("offline", entity).observe(secs)
        if _PROM:
            REFRESHES.labels("offline").inc(); LAST_TS.labels("offline").set(time.time())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["online", "offline", "both"], default="both")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true")
    g.add_argument("--loop", action="store_true")
    args = ap.parse_args()

    if args.loop:
        if _PROM:
            start_http_server(METRICS_PORT)
            print(f"metrics on :{METRICS_PORT}/metrics")
        while True:
            t0 = time.time()
            try:
                _pass(args.mode)
                print(f"refresh ok ({args.mode}) in {time.time() - t0:.1f}s")
            except Exception as e:                       # keep the loop alive
                print(f"refresh error: {e}")
            time.sleep(REFRESH_INTERVAL_SEC)
    else:
        _pass(args.mode)
        print(f"refresh done ({args.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
