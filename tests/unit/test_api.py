"""Unit tests for the API plane — no ClickHouse / MLflow needed.

Covers the fraud scorer's pure decision logic (risk banding + reason codes),
graceful behaviour when no model is registered, real-time feature assembly with
a stubbed ClickHouse, and that each service wires /health, /metrics and its
declared routes.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


# ------------------------------ risk banding ---------------------------------
@pytest.mark.parametrize("score,band", [
    (0.00, "low"), (0.29, "low"),
    (0.30, "medium"), (0.59, "medium"),
    (0.60, "high"), (0.84, "high"),
    (0.85, "critical"), (1.00, "critical"),
])
def test_risk_band_boundaries(score, band):
    from api.fraud_service.scorer import _band
    assert _band(score) == band


# ------------------------------ reason codes ---------------------------------
def test_reason_codes_fire_on_threshold_breach():
    from api.fraud_service.scorer import _reasons
    feats = {"cust_velocity_5m": 9, "geo_velocity_kmph": 800, "is_international": 1}
    codes = _reasons(feats)
    assert "customer_velocity_5m_high" in codes
    assert "impossible_travel" in codes
    assert "international_card" in codes


def test_no_reason_codes_for_benign_transaction():
    from api.fraud_service.scorer import _reasons
    feats = {"cust_velocity_5m": 1, "geo_velocity_kmph": 5, "is_international": 0}
    assert _reasons(feats) == []


def test_model_info_is_graceful_without_registry():
    """No MLflow reachable -> service still answers, reports not-loaded + features."""
    from api.fraud_service.scorer import model_info
    info = model_info()
    assert info["loaded"] is False
    assert "features" in info and len(info["features"]) == 8


# --------------------------- feature assembly --------------------------------
def test_assemble_defaults_when_no_entities():
    from api.fraud_service import features as feat
    f = feat.assemble("", "", "", amount=250.0, is_international=1)
    assert f["amount"] == 250.0
    assert f["is_international"] == 1.0
    # velocity features default to zero with no entity context
    assert f["cust_velocity_5m"] == 0.0
    assert f["merchant_velocity_1h"] == 0.0
    assert set(f) == {
        "amount", "is_international", "cust_velocity_5m", "cust_velocity_1h",
        "cust_velocity_24h", "device_velocity_1h", "merchant_velocity_1h",
        "geo_velocity_kmph"}


def test_assemble_folds_customer_velocity_buckets(monkeypatch):
    """5-minute buckets from the velocity store fold into 5m/1h/24h windows."""
    import time
    from api.fraud_service import features as feat
    now = time.time()
    buckets = [
        {"b": now - 60, "c": 3},      # within 5m, 1h, 24h
        {"b": now - 1800, "c": 4},    # within 1h, 24h
        {"b": now - 7200, "c": 5},    # within 24h only
    ]
    monkeypatch.setattr(feat.ch, "query", lambda *a, **k: buckets)
    monkeypatch.setattr(feat.ch, "query_one", lambda *a, **k: {"v": 0})
    f = feat.assemble("M1", "C1", "", amount=10.0, is_international=0)
    assert f["cust_velocity_5m"] == 3
    assert f["cust_velocity_1h"] == 7      # 3 + 4
    assert f["cust_velocity_24h"] == 12    # 3 + 4 + 5


# ------------------------------- app wiring ----------------------------------
def _routes(app):
    return {r.path for r in app.routes}


def test_fraud_app_routes():
    from fastapi.testclient import TestClient
    from api.main import app
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    assert {"/score", "/features", "/model_info", "/metrics"} <= _routes(app)


def test_merchant_app_routes():
    from api.main import app
    assert {"/merchant", "/device", "/customer/{customer_code}", "/metrics"} <= _routes(app)


def test_analytics_app_routes():
    from api.main import app
    assert {"/kpi", "/dashboard/{name}", "/metrics"} <= _routes(app)


def test_metrics_endpoint_exposes_prometheus_text():
    from fastapi.testclient import TestClient
    from api.main import app
    c = TestClient(app)
    c.get("/health")  # generate one request to record
    body = c.get("/metrics").text
    assert "api_request_duration_seconds" in body
    assert "api_requests_total" in body
