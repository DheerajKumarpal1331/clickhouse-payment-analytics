"""Merchant API — operational reads over the Postgres OLTP.
Endpoints: /merchant, /device, /customer (+ /health, /metrics)."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from api.common.metrics import instrument
from api.merchant_service import repository as repo

app = FastAPI(title="Merchant API", version="1.0",
              description="Merchant / device / customer operational data (OLTP).")
instrument(app, "merchant_service")


@app.get("/merchant")
def list_merchants(status: str | None = None, mcc: str | None = None,
                   limit: int = Query(50, le=500)):
    return {"merchants": repo.list_merchants(status, mcc, limit)}


@app.get("/merchant/{merchant_code}")
def get_merchant(merchant_code: str):
    m = repo.get_merchant(merchant_code)
    if not m:
        raise HTTPException(404, f"merchant {merchant_code} not found")
    return m


@app.get("/device")
def list_devices(merchant: str | None = None, limit: int = Query(50, le=500)):
    return {"devices": repo.list_devices(merchant, limit)}


@app.get("/device/{device_code}")
def get_device(device_code: str):
    d = repo.get_device(device_code)
    if not d:
        raise HTTPException(404, f"device {device_code} not found")
    return d


@app.get("/customer/{customer_code}")
def get_customer(customer_code: str):
    c = repo.get_customer(customer_code)
    if not c:
        raise HTTPException(404, f"customer {customer_code} not found")
    return c
