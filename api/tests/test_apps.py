"""App-wiring tests (no DB needed): the unified API imports, mounts /health +
/metrics, and exposes every domain's routes on one app. Run:
    python api/tests/test_apps.py    (needs fastapi + httpx)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient  # noqa: E402


def _routes(app):
    return {r.path for r in app.routes}


def test_unified_app_health_and_metrics():
    from api.main import app
    c = TestClient(app)
    assert c.get("/health").text == "ok"
    assert c.get("/metrics").status_code == 200
    assert c.get("/").json()["domains"] == ["fraud", "merchant", "analytics"]


def test_merchant_routes_mounted():
    from api.main import app
    assert {"/merchant", "/merchant/{merchant_code}", "/device",
            "/device/{device_code}", "/customer/{customer_code}"} <= _routes(app)


def test_analytics_routes_mounted():
    from api.main import app
    assert {"/kpi", "/dashboard/{name}"} <= _routes(app)


def test_fraud_routes_mounted():
    from api.main import app
    c = TestClient(app)
    assert {"/score", "/features", "/model_info"} <= _routes(app)
    # unknown model is graceful, not a crash
    assert c.get("/model_info").json()["loaded"] is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} API app-wiring tests passed")
