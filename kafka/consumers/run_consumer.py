"""CLI entrypoint for the ClickHouse sink consumer.

    python -m consumers.run_consumer --all
    python -m consumers.run_consumer --topics transaction_events
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config  # noqa: E402
from schemas import ALL_TOPICS  # noqa: E402
from monitoring import metrics  # noqa: E402
from consumers.consumer import ChConsumer  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--topics", help="comma-separated subset")
    ap.add_argument("--bootstrap", default=config.KAFKA_BOOTSTRAP)
    ap.add_argument("--ch-url", default=config.CH_URL)
    ap.add_argument("--ch-db", default=config.CH_DB)
    args = ap.parse_args()

    topics = ALL_TOPICS if args.all else (args.topics.split(",") if args.topics else [])
    if not topics:
        ap.error("pass --all or --topics")

    metrics.start_metrics_server(config.METRICS_PORT)
    ChConsumer(topics, args.bootstrap, args.ch_url, args.ch_db).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
