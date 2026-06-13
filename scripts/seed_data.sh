#!/usr/bin/env bash
# Seed data into the running platform (invoked by `make seed-data`).
#  - Postgres OLTP: bulk merchants/customers/devices/transactions via the
#    stored procedures (seed.py drives sp_onboard_merchant / sp_capture_transaction).
#  - ClickHouse OLAP: bulk Parquet via the data generator (loaded by the
#    OLAP-phase loader; here we just generate the files).
# Tunables via env: MERCHANTS, CUSTOMERS, TXNS, DAYS.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && { set -a; . ./.env; set +a; }

MERCH="${MERCHANTS:-2000}"; CUST="${CUSTOMERS:-50000}"; TXNS="${TXNS:-100000}"; DAYS="${DAYS:-90}"
PG_DSN="${PG_DSN:-postgresql://${POSTGRES_USER:-payments}:${POSTGRES_PASSWORD:-payments_secret}@localhost:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-payments}}"

echo "==> Postgres OLTP bulk seed (${MERCH} merchants, ${TXNS} txns)"
if python3 postgres/seed_data/seed.py --dsn "$PG_DSN" \
     --merchants "$MERCH" --customers "$CUST" --transactions "$TXNS" 2>/dev/null; then
  echo "   Postgres seeded"
else
  echo "   (needs: pip install psycopg2-binary; and 'make up' running)"
fi

echo "==> Generating ClickHouse-bound Parquet (${TXNS} txns over ${DAYS}d)"
if python3 data_generator/generate.py historical --transactions "$TXNS" --days "$DAYS" \
     --merchants "$MERCH" --customers "$CUST" --out ./data 2>/dev/null; then
  echo "   wrote ./data (load into ClickHouse with the OLAP-phase loader)"
else
  echo "   (needs: pip install -r data_generator/requirements.txt)"
fi
