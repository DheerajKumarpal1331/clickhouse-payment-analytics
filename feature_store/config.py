"""Feature store config (env-driven; matches docker/feature-store/.env.example)."""
from __future__ import annotations

import os

CH_URL = os.getenv("CH_URL", "http://analytics:analytics_secret@localhost:8123")
CH_DB = os.getenv("CH_DB", "payments")
METRICS_PORT = int(os.getenv("METRICS_PORT", "9000"))
REFRESH_INTERVAL_SEC = int(os.getenv("REFRESH_INTERVAL_SEC", "300"))

# Lookback windows (days) for rate-style features.
RATE_WINDOW_DAYS = int(os.getenv("RATE_WINDOW_DAYS", "30"))
SPEND_WINDOW_DAYS = int(os.getenv("SPEND_WINDOW_DAYS", "90"))
# Days of daily snapshots the offline backfill emits (point-in-time history).
OFFLINE_BACKFILL_DAYS = int(os.getenv("OFFLINE_BACKFILL_DAYS", "30"))

FEATURE_SET = os.getenv("FEATURE_SET", "fraud_v1")
