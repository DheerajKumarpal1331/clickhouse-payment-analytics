"""Runtime config from environment (matches docker/kafka/.env.example)."""
from __future__ import annotations

import os

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
PG_DSN = os.getenv("PG_DSN", "postgresql://payments:payments_secret@localhost:5432/payments")
CH_URL = os.getenv("CH_URL", "http://analytics:analytics_secret@localhost:8123")
CH_DB = os.getenv("CH_DB", "payments")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "ch-sink")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9000"))

# Consumer batching / reliability
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "2000"))
BATCH_MS = int(os.getenv("BATCH_MS", "2000"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))

# Producer poll batch
PRODUCER_BATCH = int(os.getenv("PRODUCER_BATCH", "5000"))
POLL_INTERVAL_SEC = float(os.getenv("POLL_INTERVAL_SEC", "2.0"))
