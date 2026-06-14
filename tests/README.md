# Testing (Phase 12)

Three tiers, gated so the fast suite runs anywhere and the heavy suites run
against the live Docker stack on demand.

```
tests/
├── conftest.py          # repo root on path; integration/load gating + fixtures
├── pytest.ini           # markers: unit / integration / load
├── requirements.txt     # pytest, locust, confluent-kafka, psycopg2
├── unit/                # no infra — runs everywhere, the CI gate
│   ├── test_etl.py      # projection SQL, watermark cursor, CH sink, DLQ, schema validation
│   ├── test_api.py      # risk banding, reason codes, feature assembly, app wiring
│   └── test_ml.py       # metrics, model factory, velocity feature SQL
├── integration/         # needs the stack — RUN_INTEGRATION=1
│   ├── test_postgres_to_kafka.py
│   ├── test_kafka_to_clickhouse.py
│   └── test_feature_store_to_model.py
└── load/                # benchmarks — RUN_LOAD=1
    ├── locustfile.py    # 100 concurrent users across the APIs
    └── kafka_load.py    # 5000 events/sec ingest throughput
```

## Unit (default — no services)

```bash
pip install -r tests/requirements.txt
pytest -c tests/pytest.ini tests/unit          # or just: pytest -c tests/pytest.ini
```

Every unit test imports and exercises real platform code (no mock-only theatre):
the Kafka projection queries, the `(wm, id)` watermark cursor, the ClickHouse
sink's request assembly, the DLQ fan-out (and that it never raises into the hot
path), schema validation, the fraud scorer's risk banding + reason codes,
real-time feature assembly, the evaluation metrics, the model factory, and the
shared velocity feature SQL.

## Integration (live stack)

```bash
docker compose up -d                          # infra
docker compose --profile pipeline up -d       # + producers/consumers (optional)
RUN_INTEGRATION=1 pytest -c tests/pytest.ini tests/integration
```

| Test | Proves |
|---|---|
| `test_postgres_to_kafka` | projection SQL runs on the live OLTP; cursor advances monotonically; event round-trips through a real broker |
| `test_kafka_to_clickhouse` | HTTP sink connects; a fact event lands via `FORMAT JSONEachRow` and is queryable; DLQ copy round-trips |
| `test_feature_store_to_model` | online store answers; real-time assembly returns the full feature vector; that vector scores through a trained model |

Connection settings come from env (`PG_DSN`, `CH_URL`, `CH_DB`, `KAFKA_BOOTSTRAP`),
defaulting to the `.env.dev` / compose values.

## Load

```bash
# 100 concurrent users (apps profile up):
RUN_LOAD=1 RUN_INTEGRATION=1 pytest -c tests/pytest.ini tests/load/kafka_load.py
locust -f tests/load/locustfile.py --host http://localhost:8003 \
       --users 100 --spawn-rate 20 --run-time 2m

# 5000 events/sec ingest benchmark:
python tests/load/kafka_load.py --count 200000 --rate-target 5000
```
