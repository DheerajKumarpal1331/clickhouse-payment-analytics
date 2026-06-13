# ClickHouse Optimization Strategy

Why the warehouse is fast on 100M+ rows, and the levers to tune it.

## 1. Partitioning & primary sort

- **`fact_transactions`**: `PARTITION BY toYYYYMMDD(event_time)`,
  `ORDER BY (merchant_id, event_time, transaction_id)`. The dominant query is
  "a merchant's transactions over a time range" → it reads a few daily
  partitions and a contiguous granule range. Daily partitions also make TTL
  eviction a cheap part-drop.
- Monthly partitions on the lower-volume facts (refunds/chargebacks/settlements/
  support/device/fraud) — fewer, larger parts, less merge overhead.
- Aggregate/velocity tables partition by day and `ORDER BY (entity, time)` to
  match their read pattern.

## 2. Column types

- **`LowCardinality(String)`** on every enum-like column (methods, codes,
  status, city, mcc, banks…) — dictionary-encoded, tiny, fast to filter/group.
- **`Decimal`** for all money (never float) — paise-accurate.
- **`ZSTD(3)`** on `user_agent` (large, repetitive); default LZ4 elsewhere.
- `event_date` is `MATERIALIZED toDate(event_time)` — free date filtering.

## 3. Skip indexes (data-skipping)

On `fact_transactions`: `bloom_filter` on `transaction_id`, `rrn`,
`customer_id`, `device_id`, `card_hash` (point lookups for disputes / fraud
review skip whole granules), and `minmax` on `amount` (range filters). These
turn needle-in-haystack lookups on a non-sort-key column into granule skips
instead of full scans.

## 4. Materialized views (pre-aggregation)

Dashboards never scan raw facts for rollups. Each MV writes `-State` partial
aggregates into an `AggregatingMergeTree` at insert time; the finalized `*_summary`
views apply `-Merge`. A daily-KPI query reads kilobytes from `agg_merchant_daily`
instead of scanning the fact. **Always query the `*_summary` / `v_*` views, never
the `agg_*` tables directly.**

## 5. Projections (`optimization/01_projections.sql`)

Method×day and network×day aggregate projections live *inside*
`fact_transactions`; ClickHouse picks them automatically for matching
group-bys, with no separate table to maintain. A sorted `proj_by_customer` is
documented but left off (storage cost vs. the bloom index already covering it).

## 6. TTL (`optimization/02_ttl_settings.sql`)

Facts age out (transactions 18mo, fraud 6mo, velocity 7d, hourly aggregates
3mo). `ttl_only_drop_parts = 1` drops whole expired parts rather than rewriting
them — the cheap path on time-partitioned data.

## 7. Operating it

`optimization/03_maintenance.sql` has ready queries for part counts (merge
pressure), per-column compression ratios, MV population checks, and in-flight
merges/mutations. The Phase 0.5 Grafana ClickHouse dashboard + Prometheus alert
(`ClickHouseTooManyParts`) watch these live.

## Scaling out (production)

Single-node here; in production `fact_transactions` becomes a `Distributed`
table over a sharded+replicated cluster, sharded by `cityHash64(merchant_id)`
so a merchant's data (and its MV state) stays co-located on one shard.
