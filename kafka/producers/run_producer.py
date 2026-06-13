"""CLI entrypoint for the CDC producer.

    python -m producers.run_producer --all
    python -m producers.run_producer --topics transaction_events,refund_events
    python -m producers.run_producer --all --once     # single pass (tests/backfill)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from schemas import ALL_TOPICS  # noqa: E402
from monitoring import metrics  # noqa: E402
from producers.producer import CdcProducer  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="stream every topic")
    ap.add_argument("--topics", help="comma-separated subset")
    ap.add_argument("--once", action="store_true", help="single pass then exit")
    ap.add_argument("--bootstrap", default=config.KAFKA_BOOTSTRAP)
    ap.add_argument("--dsn", default=config.PG_DSN)
    args = ap.parse_args()

    topics = ALL_TOPICS if args.all else (args.topics.split(",") if args.topics else [])
    if not topics:
        ap.error("pass --all or --topics")

    if not args.once:
        metrics.start_metrics_server(config.METRICS_PORT)

    prod = CdcProducer(args.bootstrap, args.dsn)
    try:
        prod.run(topics, once=args.once)
    except KeyboardInterrupt:
        pass
    finally:
        prod.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
