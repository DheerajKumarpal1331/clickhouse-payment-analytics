# FastAPI Services (Phase 8)

Three services expose the platform. One shared image (`docker/api/Dockerfile`)
serves any of them — the `SERVICE` env selects which app uvicorn runs
(`api.${SERVICE}.main:app`), so `merchant-api`, `analytics-api`, `fraud-api`
(compose `apps` profile) all run the same image.

| Service | Endpoints | Reads |
|---|---|---|
| **merchant_service** | `/merchant`, `/merchant/{code}`, `/device`, `/device/{code}`, `/customer/{code}` | Postgres OLTP |
| **fraud_service** | `POST /score`, `GET /features`, `GET /model_info` | ClickHouse velocity store + MLflow model |
| **analytics_service** | `/kpi`, `/dashboard/{name}` | ClickHouse marts |

Every service also exposes `/health` and `/metrics` (Prometheus, scraped by the
platform Prometheus `services` job).

## Layout

```
api/
├── common/             config, ClickHouse + Postgres clients, Prometheus middleware
├── merchant_service/   repository (OLTP SQL) + main
├── fraud_service/      features (real-time velocity assembly) + scorer (model) + main
└── analytics_service/  queries (mart SQL) + main
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

SERVICE=merchant_service  uvicorn api.merchant_service.main:app  --port 8001
SERVICE=analytics_service uvicorn api.analytics_service.main:app --port 8002
SERVICE=fraud_service     uvicorn api.fraud_service.main:app     --port 8003
```

Containerized: `docker compose --profile apps up -d` (merchant-api :8001,
analytics-api :8002, fraud-api :8003). OpenAPI docs at each service's `/docs`.
