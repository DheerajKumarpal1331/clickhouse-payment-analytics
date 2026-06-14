"""Fraud API — real-time scoring + feature inspection.
Endpoints: /score, /features, /model_info (+ /health, /metrics). Target <100ms."""
from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.fraud_service import features as feat, scorer

router = APIRouter(tags=["fraud"])


class ScoreRequest(BaseModel):
    transaction_id: str = ""
    merchant_id: str
    customer_id: str = ""
    device_id: str = ""
    amount: float = Field(gt=0)
    is_international: int = 0
    latitude: float = 0.0
    longitude: float = 0.0


@router.post("/score")
def score(req: ScoreRequest):
    return scorer.score(req.merchant_id, req.customer_id, req.device_id,
                        req.amount, req.is_international, req.latitude, req.longitude)


@router.get("/features")
def features(merchant_id: str = "", customer_id: str = "", device_id: str = "",
             amount: float = Query(0.0), is_international: int = 0):
    """Inspect the assembled feature vector for given entities (debug/ops)."""
    return feat.assemble(merchant_id, customer_id, device_id, amount, is_international)


@router.get("/model_info")
def model_info():
    return scorer.model_info()
