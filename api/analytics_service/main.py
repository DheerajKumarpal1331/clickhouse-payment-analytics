"""Analytics API — KPIs + dashboard payloads from the ClickHouse marts.
Endpoints: /kpi, /dashboard/{name} (+ /health, /metrics)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.analytics_service import queries as q

router = APIRouter(tags=["analytics"])


@router.get("/kpi")
def kpi(days: int = Query(30, ge=1, le=365)):
    """Headline platform KPIs (TPV, revenue, transactions, active merchants, fraud)."""
    return {"window_days": days, "kpis": q.kpis(days), "timeseries": q.timeseries(days)}


@router.get("/dashboard/{name}")
def dashboard(name: str, days: int = Query(30, ge=1, le=365)):
    """Full payload for a named dashboard: executive | fraud | settlement | operations."""
    builder = q.DASHBOARDS.get(name)
    if builder is None:
        raise HTTPException(404, f"unknown dashboard '{name}'; "
                                 f"choose from {sorted(q.DASHBOARDS)}")
    return {"dashboard": name, "window_days": days, **builder(days)}
