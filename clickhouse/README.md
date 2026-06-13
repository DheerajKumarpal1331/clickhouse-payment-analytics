# ClickHouse Analytics Warehouse (Phase 5)

The OLAP layer: the Kafka consumer (Phase 4) streams events in, materialized
views pre-aggregate at insert time, and marts serve the dashboards.

## Layout

| Folder | Contents |
|---|---|
| `ddl/` | database, **7 dimensions** (3 SCD-1 + 4 static, populated as IaC), **7 wide fact tables** |
| `materialized_views/` | **7 MVs** (merchant hourly/daily/monthly, merchant_risk, fraud_feature, device_health, settlement) — each `AggregatingMergeTree` target + MV + finalized `*_summary` view |
| `features/` | ML feature store (offline PIT + online latest) + 5-min velocity aggregates + 1h rolling view |
| `marts/` | dashboard-ready views: executive KPIs, merchant 360, fraud, settlement, operations |
| `optimization/` | projections, TTL/settings, maintenance queries + strategy doc |

## Star schema

```
        dim_merchants  dim_customers  dim_devices  dim_dates
        dim_geography  dim_payment_method  dim_risk_level
                              │
        ┌──────────┬──────────┼──────────┬───────────┬───────────┐
   fact_transactions  fact_refunds  fact_chargebacks  fact_settlements
   fact_fraud_events  fact_support_events  fact_device_events
```

`fact_transactions` is the wide processor record (~90 cols: ISO 8583, EMV, 3DS,
fee breakdown, settlement linkage, device/network telemetry, geo). The Kafka
consumer inserts `JSONEachRow` with skip-unknown + null-as-default, so the
narrow OLTP-CDC event fills the core and the generator's wide payload fills
everything — same table.

## Apply / run

```bash
# Auto-applied on first `docker compose up -d` (init mounts ./clickhouse -> /warehouse).
# Re-apply to a running container:
make init-clickhouse        # = bash docker/clickhouse/apply.sh

# Order: ddl -> materialized_views -> features -> marts -> optimization (all idempotent)
```

## Query contract

Dashboards read the **`*_summary` / `mart_*` / `v_*` views** — never the
`agg_*` aggregate tables directly (those hold `-State` partials that only make
sense through `-Merge`). See `optimization/README.md` for why it's fast.
