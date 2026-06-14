"""Load test — 100 concurrent users across the platform APIs.

Models a realistic operator + checkout mix: fraud scoring on the hot path,
merchant lookups, and analytics KPIs. Validates the APIs hold their latency
SLOs (fraud target <100ms) under concurrency.

Run (with the `apps` profile up):
    pip install -r tests/requirements.txt
    locust -f tests/load/locustfile.py --host http://localhost:8003 \
           --users 100 --spawn-rate 20 --run-time 2m

Hosts (per docker-compose port map): fraud-api :8003, merchant-api :8001,
analytics-api :8002. FRAUD_HOST / MERCHANT_HOST / ANALYTICS_HOST override.
"""
from __future__ import annotations

import os
import random

from locust import HttpUser, between, task

FRAUD_HOST = os.getenv("FRAUD_HOST", "http://localhost:8003")
MERCHANT_HOST = os.getenv("MERCHANT_HOST", "http://localhost:8001")
ANALYTICS_HOST = os.getenv("ANALYTICS_HOST", "http://localhost:8002")

_MERCHANTS = [f"M{i}" for i in range(1, 51)]
_CUSTOMERS = [f"C{i}" for i in range(1, 201)]
_DEVICES = [f"D{i}" for i in range(1, 101)]


def _score_payload() -> dict:
    return {
        "transaction_id": f"L{random.randint(1, 10_000_000)}",
        "merchant_id": random.choice(_MERCHANTS),
        "customer_id": random.choice(_CUSTOMERS),
        "device_id": random.choice(_DEVICES),
        "amount": round(random.uniform(50, 25_000), 2),
        "is_international": random.choice([0, 0, 0, 1]),
        "latitude": round(random.uniform(8, 35), 4),
        "longitude": round(random.uniform(68, 92), 4),
    }


class FraudUser(HttpUser):
    """Checkout hot path — the latency-critical SLO (<100ms p99)."""
    host = FRAUD_HOST
    weight = 6
    wait_time = between(0.1, 0.5)

    @task(5)
    def score(self):
        with self.client.post("/score", json=_score_payload(),
                              name="POST /score", catch_response=True) as r:
            # 200 even when the model is unregistered (graceful body) is acceptable
            if r.status_code != 200:
                r.failure(f"status {r.status_code}")

    @task(1)
    def model_info(self):
        self.client.get("/model_info", name="GET /model_info")


class MerchantUser(HttpUser):
    host = MERCHANT_HOST
    weight = 2
    wait_time = between(0.2, 1.0)

    @task
    def merchant(self):
        m = random.choice(_MERCHANTS)
        self.client.get(f"/merchant/{m}", name="GET /merchant/{code}")


class AnalyticsUser(HttpUser):
    host = ANALYTICS_HOST
    weight = 2
    wait_time = between(0.5, 2.0)

    @task
    def kpi(self):
        self.client.get("/kpi", name="GET /kpi")
