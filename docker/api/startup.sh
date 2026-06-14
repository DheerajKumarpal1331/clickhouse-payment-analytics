#!/usr/bin/env bash
# Serve the unified Payment Analytics API (api/main.py:app) on :8000.
# All three domains — fraud / merchant / analytics — are mounted in one app.
set -e
WORKERS="${UVICORN_WORKERS:-2}"
echo "starting payment-analytics-api on :8000 ($WORKERS workers)"
exec uvicorn "api.main:app" --host 0.0.0.0 --port 8000 --workers "$WORKERS"
