#!/usr/bin/env bash
# Apply the ClickHouse warehouse DDL to a RUNNING container (used by
# `make init-clickhouse`). Order matters: ddl -> materialized_views ->
# features -> marts -> optimization. All DDL is IF NOT EXISTS / idempotent.
#
# Usage (host):   bash docker/clickhouse/apply.sh
#   honors CLICKHOUSE_USER / CLICKHOUSE_PASSWORD from the environment.
set -euo pipefail
cd "$(dirname "$0")/../.."          # repo root
[ -f .env ] && { set -a; . ./.env; set +a; }

USER="${CLICKHOUSE_USER:-analytics}"
PASS="${CLICKHOUSE_PASSWORD:-analytics_secret}"
CONTAINER="${CH_CONTAINER:-payments-clickhouse}"

run() { docker exec -i "$CONTAINER" clickhouse-client -u "$USER" --password "$PASS" --multiquery; }

for dir in ddl materialized_views features marts optimization; do
  for f in clickhouse/$dir/*.sql; do
    [ -e "$f" ] || continue
    echo ">> $f"
    run < "$f"
  done
done
echo "ClickHouse warehouse applied."
