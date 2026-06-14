"""Unified Payment Analytics API — one FastAPI app mounting all three domains
(fraud scoring, merchant/OLTP reads, analytics/marts) behind a single port.

Consolidated from the former three microservices: the endpoint paths don't
collide, so routers are included at the root and every previous path is
unchanged (/score, /merchant, /kpi, ...). One Prometheus /metrics + /health
covers the whole surface. Served by gunicorn/uvicorn as `api.main:app`.

Each router is included defensively: a backend that isn't reachable at import
time (e.g. MLflow for the fraud model) must not take down the other domains.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from api.common.metrics import instrument

log = logging.getLogger("api")

app = FastAPI(
    title="Payment Analytics API",
    version="2.0",
    description="Fraud scoring · merchant/OLTP reads · analytics marts — unified.",
)
instrument(app, "payments_api")


def _include(module_path: str, label: str) -> None:
    try:
        module = __import__(module_path, fromlist=["router"])
        app.include_router(module.router)
        log.info("mounted %s router", label)
    except Exception as exc:  # one domain's import must not blank the others
        log.error("failed to mount %s router: %s", label, exc)


_include("api.fraud_service.main", "fraud")
_include("api.merchant_service.main", "merchant")
_include("api.analytics_service.main", "analytics")


@app.get("/", include_in_schema=False)
def root():
    return {
        "service": "payment-analytics-api",
        "domains": ["fraud", "merchant", "analytics"],
        "docs": "/docs",
        "metrics": "/metrics",
        "health": "/health",
    }
