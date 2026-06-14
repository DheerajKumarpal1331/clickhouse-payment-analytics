# Unified API (Phase 8)

One FastAPI app (`api/main.py`) serves all three domains behind a single port.
The domains are independent `APIRouter`s included at the root — the paths don't
collide, so every endpoint keeps its original path. Consolidated from the former
three microservices (merchant / analytics / fraud); one image, one `/metrics`,
one `/health`.

| Domain | Endpoints | Reads |
|---|---|---|
| **merchant** | `/merchant`, `/merchant/{code}`, `/device`, `/device/{code}`, `/customer/{code}` | Postgres OLTP |
| **fraud** | `POST /score`, `GET /features`, `GET /model_info` | ClickHouse velocity store + MLflow model |
| **analytics** | `/kpi`, `/dashboard/{name}` | ClickHouse marts |

The app also exposes `/`, `/health` and `/metrics` (Prometheus, scraped by the
platform Prometheus `services` job — latency labeled by `route`).

## Layout

```
api/
├── main.py             unified app: instruments + includes the three routers
├── common/             config, ClickHouse + Postgres clients, Prometheus middleware
├── merchant_service/   repository (OLTP SQL) + router
├── fraud_service/      features (real-time velocity assembly) + scorer (model) + router
└── analytics_service/  queries (mart SQL) + router
```

## Fraud scoring path (`<100ms` target)

`POST /score` assembles the model's velocity features for the *incoming* txn
from a few indexed ClickHouse lookups (customer/device buckets in
`agg_velocity_5m`, merchant hourly rollup, the customer's last txn for geo
speed), loads the Production model from the MLflow registry, predicts, and
returns `{fraud_score, risk_level, reason_codes, model_version, latency_ms}`.
Training/serving feature parity is guaranteed by reusing `ml.config.FEATURE_COLUMNS`.

## Run

```bash
pip install -r api/requirements.txt
export PG_DSN=postgresql://payments:payments_secret@localhost:5432/payments
export CH_URL=http://analytics:analytics_secret@localhost:8123
export MLFLOW_TRACKING_URI=http://localhost:5000

uvicorn api.main:app --port 8000
```

Containerized: `docker compose --profile apps up -d` (the `api` service on
:8000). OpenAPI docs at http://localhost:8000/docs.
