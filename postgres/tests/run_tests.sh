#!/usr/bin/env bash
# Run the OLTP test suite against a database that already has the schema
# + procedures + seed loaded (e.g. after ../apply.sh).
#
# Tests use plpgsql ASSERT and expected-exception blocks; any failure RAISEs
# and -v ON_ERROR_STOP=1 makes psql exit non-zero, failing CI.
#
# Usage: PGDSN=postgresql://postgres:postgres@localhost:5432/payments ./run_tests.sh
set -euo pipefail

PGDSN="${PGDSN:-postgresql://postgres:postgres@localhost:5432/payments}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail=0

for t in "$HERE"/0*_*.sql; do
  echo "=========================================="
  echo "RUN $(basename "$t")"
  if psql "$PGDSN" -v ON_ERROR_STOP=1 -q -f "$t"; then
    echo "  -> OK"
  else
    echo "  -> FAILED"
    fail=1
  fi
done

echo "=========================================="
[ "$fail" -eq 0 ] && echo "ALL TESTS PASSED" || { echo "SOME TESTS FAILED"; exit 1; }
