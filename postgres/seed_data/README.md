# Seed Data

Two seeders, same outcome — a working OLTP dataset that exercises the real
stored procedures and triggers:

| File | Driver | Use for |
|---|---|---|
| `01_reference_data.sql` | none (psql) | **Required first.** MCCs, banks, networks, BINs, locations, payment methods, terminal capabilities, fraud rules. FK prerequisite for everything else. |
| `02_sample_seed.sql` | none (psql) | **Default.** ~200 merchants, ~2k customers, ~5k transactions with full lifecycle. Validated; deterministic-ish; fast. |
| `seed.py` | `psycopg2` | Larger / configurable volume (`--merchants --customers --transactions`). |

## Order

Seed runs **after** schema + procedures are loaded:

```
ddl/  →  indexes/  →  procedures/  →  seed_data/01_reference_data.sql  →  seed_data/02_sample_seed.sql
```

`../apply.sh` does this whole chain for you.

## Quick start

```bash
# from repo root, against a running Postgres
psql "$PGDSN" -f postgres/seed_data/01_reference_data.sql
psql "$PGDSN" -f postgres/seed_data/02_sample_seed.sql

# or the larger Python seeder
pip install psycopg2-binary
python postgres/seed_data/seed.py --dsn "$PGDSN" --merchants 1000 --transactions 50000
```

## What it proves

Loading the sample seed isn't just data insertion — it drives:

- `sp_onboard_merchant` → atomic 5-table merchant creation
- the `merchant_master` UPDATE → fires status-history + audit triggers
- `sp_capture_transaction` → state machine + `capture_records` + `sp_compute_fees`
- `sp_process_refund` → approval + refund txn + status history + header state change
- `sp_build_settlement_batch` → per-merchant netting into `merchant_settlements`

So a green seed = the whole OLTP write path works end to end.

## Scale note

This seeds a **representative sample**, not 100M rows. High-volume history is an
OLAP concern: the data generator (`../../data_generator/`) produces 10M+
transactions straight into ClickHouse via Kafka. Forcing 100M rows through the
normalized OLTP write path is neither realistic (a real OLTP holds hot/recent
data; cold history is archived) nor necessary for demonstrating the schema.
