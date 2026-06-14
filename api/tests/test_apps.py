"""App-wiring tests (no DB needed): each service imports, mounts /health +
/metrics, and exposes its declared routes. Run:
    python api/tests/test_apps.py    (needs fastapi + httpx)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402


def _routes(app):
    return {r.path for r in app.routes}


def test_merchant_app():
    from api.merchant_service.main import app
    c = TestClient(app)
    assert c.get("/health").text == "ok"
    assert {"/merchant", "/merchant/{merchant_code}", "/device",
            "/device/{device_code}", "/customer/{customer_code}", "/metrics"} <= _routes(app)


def test_analytics_app():
    from api.analytics_service.main import app
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    assert {"/kpi", "/dashboard/{name}", "/metrics"} <= _routes(app)


def test_fraud_app():
    from api.fraud_service.main import app
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    assert {"/score", "/features", "/model_info", "/metrics"} <= _routes(app)
    # unknown model is graceful, not a crash
    assert c.get("/model_info").json()["loaded"] is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} API app-wiring tests passed")
