"""Fraud-serving entrypoint (fraud-serving container).

Loads the Production model from the MLflow registry and exposes a minimal
scoring service: GET /health, GET /model-info, POST /predict (feature dict ->
probability + risk band). The public Phase-8 fraud API can call this or load
the model the same way. Requires fastapi + mlflow (present in the container).
"""
from __future__ import annotations

import os

from ml.config import MODEL_NAME

RISK_BANDS = [(0.85, "critical"), (0.60, "high"), (0.30, "medium"), (0.0, "low")]


def band(score: float) -> str:
    for lo, name in RISK_BANDS:
        if score >= lo:
            return name
    return "low"


def load_model():
    import mlflow.pyfunc
    uri = os.getenv("MODEL_URI", f"models:/{MODEL_NAME}/Production")
    return mlflow.pyfunc.load_model(uri), uri


def build_app():
    from fastapi import FastAPI
    from pydantic import BaseModel
    import pandas as pd

    from ml.config import FEATURE_COLUMNS

    app = FastAPI(title="Fraud Serving", version="1.0")
    state: dict = {}

    class Features(BaseModel):
        features: dict

    @app.on_event("startup")
    def _startup():
        try:
            state["model"], state["uri"] = load_model()
        except Exception as e:                      # serve /health even if no model yet
            state["error"] = str(e)

    @app.get("/health")
    def health():
        return {"status": "ok", "model_loaded": "model" in state}

    @app.get("/model-info")
    def model_info():
        return {"model_name": MODEL_NAME, "model_uri": state.get("uri"),
                "loaded": "model" in state, "error": state.get("error")}

    @app.post("/predict")
    def predict(req: Features):
        model = state.get("model")
        if model is None:
            return {"error": "model not loaded", "detail": state.get("error")}
        row = {c: float(req.features.get(c, 0.0)) for c in FEATURE_COLUMNS}
        score = float(model.predict(pd.DataFrame([row]))[0])
        return {"fraud_score": round(score, 4), "risk_level": band(score)}

    return app


def main() -> int:
    import uvicorn
    uvicorn.run(build_app(), host="0.0.0.0", port=int(os.getenv("PORT", "8500")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
