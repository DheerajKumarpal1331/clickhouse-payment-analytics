#!/usr/bin/env bash
# Serve the Dash app (dashboard/app.py:server is the Flask WSGI handle).
set -e
exec gunicorn dashboard.app:server --bind 0.0.0.0:8050 --workers "${DASH_WORKERS:-2}" --timeout 120
