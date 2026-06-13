#!/usr/bin/env bash
# ============================================================
# Postgres IaC bootstrap — runs ONCE on first container init
# (Postgres entrypoint executes /docker-entrypoint-initdb.d/* on an
# empty data dir). Creates side databases then applies the Phase-2
# OLTP schema in dependency order: ddl -> indexes -> procedures -> seed.
# ============================================================
set -euo pipefail

PROJ=/project/postgres
PG() { psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" "$@"; }

echo "==> creating side databases: ${POSTGRES_EXTRA_DBS:-<none>}"
IFS=',' read -ra DBS <<< "${POSTGRES_EXTRA_DBS:-}"
for db in "${DBS[@]}"; do
  db="$(echo "$db" | xargs)"; [ -z "$db" ] && continue
  # CREATE DATABASE can't run in a txn or with IF NOT EXISTS — check then create.
  if PG -tAc "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1; then
    echo "    = $db (exists)"
  else
    PG -c "CREATE DATABASE \"$db\""
    echo "    + $db"
  fi
done

echo "==> applying OLTP schema into '$POSTGRES_DB'"
run_dir() { for f in "$PROJ/$1"/*.sql; do [ -e "$f" ] || continue; echo "    > $1/$(basename "$f")"; PG -f "$f"; done; }
run_dir ddl
run_dir indexes
run_dir procedures
# reference + sample seed (bulk volume is loaded separately via seed.py)
for f in "$PROJ/seed_data/01_reference_data.sql" "$PROJ/seed_data/02_sample_seed.sql"; do
  [ -e "$f" ] && { echo "    > seed_data/$(basename "$f")"; PG -f "$f"; }
done

echo "==> Postgres OLTP ready: $(PG -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema IN ('merchant','device','customer','txn','settlement','refund','chargeback','fraud','support','ref')") tables"
