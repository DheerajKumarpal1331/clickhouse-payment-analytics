#!/usr/bin/env bash
# IaC: on FIRST ClickHouse init, build the full warehouse (dims, facts,
# materialized views, features, marts, optimizations). The clickhouse/ tree is
# mounted read-only at /warehouse by docker-compose. Runs after 01-init.sql
# (which created the database + DLQ sink).
set -euo pipefail

WAREHOUSE=/warehouse
[ -d "$WAREHOUSE" ] || { echo "no /warehouse mount; skipping warehouse build"; exit 0; }

ch() { clickhouse-client --multiquery; }   # init runs as default with access

for dir in ddl materialized_views features marts optimization; do
  for f in "$WAREHOUSE/$dir"/*.sql; do
    [ -e "$f" ] || continue
    echo "warehouse >> $dir/$(basename "$f")"
    ch < "$f"
  done
done
echo "ClickHouse warehouse provisioned (IaC)."
