"""Shared API config (env-driven; matches docker/api/.env.example)."""
from __future__ import annotations

import os

SERVICE = os.getenv("SERVICE", "merchant_service")
PG_DSN = os.getenv("PG_DSN", "postgresql://payments:payments_secret@localhost:5432/payments")
CH_URL = os.getenv("CH_URL", "http://analytics:analytics_secret@localhost:8123")
CH_DB = os.getenv("CH_DB", "payments")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
MODEL_NAME = os.getenv("MODEL_NAME", "fraud_detector")
MODEL_STAGE = os.getenv("MODEL_STAGE", "Production")
