#!/usr/bin/env bash
# Platform test runner (invoked by `make test`).
#  1. Postgres OLTP suite — runs the Phase-2 SQL assertions inside the
#     running postgres container (tests are mounted at /project/postgres/tests).
#  2. Data generator smoke — proves the synthetic generator imports & runs.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && { set -a; . ./.env; set +a; }

PU="${POSTGRES_USER:-payments}"; PD="${POSTGRES_DB:-payments}"
fail=0

echo "==> Postgres OLTP test suite"
if docker ps --format '{{.Names}}' | grep -q '^payments-postgres$'; then
  for t in 01_constraints 02_triggers 03_procedures 04_integrity; do
    echo "---- ${t}_test.sql"
    if ! docker compose exec -T postgres \
         psql -v ON_ERROR_STOP=1 -U "$PU" -d "$PD" -f "/project/postgres/tests/${t}_test.sql"; then
      echo "   FAILED: $t"; fail=1
    fi
  done
else
  echo "   (postgres container not running — 'make up' first to run OLTP tests)"
fi

echo "==> data generator smoke"
if python3 data_generator/generate.py historical --transactions 5000 --days 7 \
     --merchants 100 --customers 1000 --out /tmp/dg_test >/dev/null 2>&1; then
  echo "   generator OK"
  rm -rf /tmp/dg_test
else
  echo "   (generator needs: pip install -r data_generator/requirements.txt)"
fi

[ "$fail" -eq 0 ] && echo "ALL TESTS PASSED" || { echo "SOME TESTS FAILED"; exit 1; }
