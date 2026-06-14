"""Scoring: load the Production model from the MLflow registry (lazy, cached),
assemble features, predict, derive risk band + rules-based reason codes. If no
model is registered yet the service stays up and reports it (graceful)."""
from __future__ import annotations

import time

from api.common.config import MLFLOW_TRACKING_URI, MODEL_NAME, MODEL_STAGE
from api.fraud_service import features as feat
from ml.config import FEATURE_COLUMNS

_model = None
_model_meta: dict = {"loaded": False}

# Lightweight, explainable reason codes (no SHAP needed at serve time).
_REASON_RULES = [
    ("cust_velocity_5m", 8, "customer_velocity_5m_high"),
    ("cust_velocity_1h", 20, "customer_velocity_1h_high"),
    ("device_velocity_1h", 15, "device_velocity_1h_high"),
    ("merchant_velocity_1h", 500, "merchant_velocity_1h_high"),
    ("geo_velocity_kmph", 700, "impossible_travel"),
    ("is_international", 1, "international_card"),
]


def _load():
    global _model, _model_meta
    if _model is not None:
        return _model
    import mlflow
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    uri = f"models:/{MODEL_NAME}/{MODEL_STAGE}"
    _model = mlflow.pyfunc.load_model(uri)
    meta = {"loaded": True, "model_name": MODEL_NAME, "stage": MODEL_STAGE, "uri": uri}
    try:
        v = mlflow.tracking.MlflowClient().get_latest_versions(MODEL_NAME, [MODEL_STAGE])
        if v:
            meta["version"] = v[0].version
    except Exception:
        pass
    _model_meta = meta
    return _model


def model_info() -> dict:
    try:
        _load()
    except Exception as e:
        return {"loaded": False, "model_name": MODEL_NAME, "error": str(e),
                "features": FEATURE_COLUMNS}
    return {**_model_meta, "features": FEATURE_COLUMNS}


def _band(score: float) -> str:
    return ("critical" if score >= 0.85 else "high" if score >= 0.60
            else "medium" if score >= 0.30 else "low")


def _reasons(features: dict) -> list[str]:
    return [code for col, thr, code in _REASON_RULES if features.get(col, 0) >= thr]


def score(merchant_id: str, customer_id: str, device_id: str, amount: float,
          is_international: int, latitude: float, longitude: float) -> dict:
    t0 = time.perf_counter()
    f = feat.assemble(merchant_id, customer_id, device_id, amount,
                      is_international, latitude, longitude)
    try:
        import pandas as pd
        model = _load()
        prob = float(model.predict(pd.DataFrame([f])[FEATURE_COLUMNS])[0])
    except Exception as e:
        return {"error": f"model unavailable: {e}", "features": f}
    return {
        "fraud_score": round(prob, 4),
        "risk_level": _band(prob),
        "reason_codes": _reasons(f),
        "features": f,
        "model_version": _model_meta.get("version"),
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
    }
