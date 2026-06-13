#!/usr/bin/env bash
# Apply the full OLTP schema in dependency order:
#   ddl (structure+constraints) -> indexes -> procedures -> seed.
# Usage: PGDSN=postgresql://user:pass@host:5432/payments ./apply.sh [--no-seed]
set -euo pipefail

PGDSN="${PGDSN:-postgresql://postgres:postgres@localhost:5432/payments}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NO_SEED="${1:-}"

run() { echo ">> $1"; psql "$PGDSN" -v ON_ERROR_STOP=1 -q -f "$1"; }

echo "== DDL =="
for f in "$HERE"/ddl/*.sql; do run "$f"; done
echo "== Indexes =="
for f in "$HERE"/indexes/*.sql; do run "$f"; done
echo "== Procedures =="
for f in "$HERE"/procedures/*.sql; do run "$f"; done

if [ "$NO_SEED" != "--no-seed" ]; then
  echo "== Seed =="
  run "$HERE/seed_data/01_reference_data.sql"
  run "$HERE/seed_data/02_sample_seed.sql"
fi

echo "OK"
