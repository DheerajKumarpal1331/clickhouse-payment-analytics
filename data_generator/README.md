# Synthetic Data Generator

Generates a realistic Indian payment ecosystem — merchants, customers, POS
devices, and transactions with downstream refunds & chargebacks — at portfolio
scale. Output is **Parquet** (for ClickHouse backfill), a live **Kafka** stream,
or a continuous **Postgres** feed (`live_postgres.py`) that drives the whole
pipeline end-to-end.

## Modules (Phase 3 deliverables)

| File | Produces |
|---|---|
| `merchant_generator.py` | merchant master: KYC, per-method MDR, risk tier, lifecycle |
| `customer_generator.py` | customers: demographics, hashed PII, device fingerprint, risk |
| `device_generator.py` | POS terminals bound to merchants (smartpos / soundbox / mPOS / e-com) |
| `transaction_generator.py` | the core stream with temporal shaping + fraud injection |
| `fraud_generator.py` | fraud bursts: velocity, card-testing, device-takeover, geo-anomaly, collusion, refund-abuse |
| `refund_generator.py` | refunds (incl. abusive) + chargebacks |
| `reference.py` | shared constants, holiday calendar, hour/day curves |
| `enrichment.py` | ISO 8583 / EMV / 3DS / fee fields per transaction (~95 cols) |
| `generate.py` | CLI orchestrator |

## Realism modeled

- **Merchant behaviour** — grocery / fuel / pharmacy / restaurant / hospital /
  e-commerce / electronics / retail, each with its own MCC, average ticket and
  risk base; high-volume merchants dominate volume (Zipf-ish).
- **Transaction patterns** — intraday curve (lunch + evening peaks, pre-dawn
  trough), **weekend** uplift, **holiday** spikes (national + Diwali windows),
  **festive season** (Oct–Nov), and **salary days** (spend surges on the 1st–5th
  and again at month-end, matching Indian pay cycles).
- **Fraud patterns** — velocity attacks, card testing, device takeover, geo
  anomalies, merchant collusion, refund abuse — each emitted as a correlated
  burst with exact `fraud_label` / `fraud_scenario` tags.

## Scale

| Entity | Target | Flag |
|---|---|---|
| Merchants | 100,000 | `--merchants 100000` |
| Devices | ~500,000 | derived (≈2–5 per merchant) |
| Customers | 5,000,000 | `--customers 5000000` |
| Transactions | 100,000,000 | `--transactions 100_000_000` |
| History | 3 years | `--days 1095` |

```bash
pip install -r requirements.txt

# demo scale (fast, single process)
python generate.py historical --transactions 100000 --days 30 \
    --merchants 500 --customers 5000 --out ./data

# full portfolio scale, parallelized
python generate.py historical --transactions 100_000_000 --days 1095 \
    --merchants 100000 --customers 5000000 --out ./data --workers 8
```

### Continuous live feed → Postgres (`live_postgres.py`)

Drives the platform **live**: streams fresh transactions into
`txn.transaction_header` and periodically onboards new merchants into
`merchant.merchant_master`, sampling existing FK keys. The watermark-CDC
producer carries these to Kafka → ClickHouse → the dashboards.

```bash
# standalone (≈32 txns/sec, a new merchant every 25s)
PG_DSN=postgresql://payments:payments_secret@localhost:5432/payments \
    python -m data_generator.live_postgres --rate 8 --batch 4 --merchant-every 25

# or via compose (pipeline profile): the `data-generator` service
GEN_RATE=8 GEN_BATCH=4 docker compose --profile pipeline up -d data-generator
```

### Throughput & memory notes (engineering honesty)

- Generation is **enrichment-bound** (~95 fields, hashing, formatting per row),
  not sampling-bound — sampling is O(log n) via precomputed cumulative weights +
  bisect. Expect tens of thousands of rows/sec/core.
- `--workers N` shards the transaction target across processes. Each worker
  **rebuilds the deterministic world** (same seeds → consistent merchant/customer
  IDs) and writes its own `transactions_wK_*.parquet` parts.
- 5M customers held in memory is multiple GB **per process**; for very large
  worker counts on a small box, reduce `--customers` or `--workers`. The
  dimensions are written once by the parent; only facts are parallelized.

## Output → ClickHouse

Parquet parts load straight into `payments.fact_transactions` (column-name
matched). The dims load into `dim_merchants` / `dim_customers` / `dim_devices`.
See `../clickhouse/` and the Phase 4 loader.
