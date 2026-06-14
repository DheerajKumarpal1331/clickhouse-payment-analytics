"""Prometheus instrumentation shared by all services. Adds a latency histogram
+ request counter (labeled by service/route/method/status) and a /metrics
endpoint scraped by the platform Prometheus (job: services)."""
from __future__ import annotations

import time

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse, Response

REQUESTS = Counter("api_requests_total", "API requests",
                   ["service", "route", "method", "status"])
LATENCY = Histogram("api_request_duration_seconds", "API request latency",
                    ["service", "route"],
                    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))


def instrument(app, service: str) -> None:
    class _Mw(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            route = request.url.path
            t0 = time.perf_counter()
            resp = await call_next(request)
            LATENCY.labels(service, route).observe(time.perf_counter() - t0)
            REQUESTS.labels(service, route, request.method, resp.status_code).inc()
            return resp

    app.add_middleware(_Mw)

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/health", include_in_schema=False)
    def health():
        return PlainTextResponse("ok")
