#!/usr/bin/env bash
# Serve the FastAPI app selected by $SERVICE (merchant_api|analytics_api|fraud_api).
# Each maps to api/<service>/main.py:app (delivered in the API phase).
set -e
SERVICE="${SERVICE:-merchant_api}"
WORKERS="${UVICORN_WORKERS:-2}"
echo "starting $SERVICE on :8000 ($WORKERS workers)"
exec uvicorn "api.${SERVICE}.main:app" --host 0.0.0.0 --port 8000 --workers "$WORKERS"
