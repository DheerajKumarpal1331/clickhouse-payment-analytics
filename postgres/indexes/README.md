# Indexing Strategy

Performance indexes are kept here, separate from `../ddl/` (which holds table
structure and **correctness** constraints — PK / FK / UNIQUE / EXCLUDE /
business-rule partial-uniques). This separation makes the indexing strategy a
reviewable artifact and lets you tune indexes without touching schema DDL.

Apply **after** the tables exist: `ddl/ → indexes/ → procedures/`. All use
`CREATE INDEX IF NOT EXISTS` so re-runs are safe.

## Principles

1. **Index the access path, not the column.** Composite indexes are ordered to
   match real query predicates + sort, e.g. `idx_txn_merchant_time
   (merchant_id, created_at DESC)` serves "a merchant's recent transactions" —
   the single most common OLTP query — with one index-only range scan.

2. **Partial indexes for skewed predicates.** We only ever scan a thin slice for
   some queries, so we only index that slice — far smaller and faster to
   maintain than a full index:
   - `idx_txn_failed … WHERE NOT is_success`
   - `idx_txn_fraud … WHERE fraud_label` (~0.4% of rows)
   - `idx_fraud_alert_open … WHERE status = 'open'`
   - `idx_cb_open_due … WHERE status = 'open'`
   - `idx_sla_breached … WHERE NOT breached`

3. **FK columns get indexed.** Postgres does **not** auto-index the referencing
   side of a foreign key. Every child→parent join column (`*_fk`) has an index,
   so header→detail joins and cascade checks stay fast.

4. **GIN trigram for fuzzy search.** `idx_merchant_name_trgm` powers
   `ILIKE '%query%'` merchant search in the ops console (needs `pg_trgm`).

5. **Partitioned-table indexes propagate.** Indexes on `txn.transaction_header`
   are declared on the parent; Postgres creates a matching local index on every
   monthly partition automatically.

## What is deliberately NOT indexed

- Low-cardinality boolean/enum columns without a partial predicate — a full
  index there rarely beats a seq scan and slows writes.
- Wide audit/history tables beyond their `(entity, time)` access key — they are
  append-only and queried rarely.

## Index inventory by module

| File | Module | Notable indexes |
|---|---|---|
| `01_merchant_indexes.sql` | Merchant | status, mcc, trigram name search, satellites, audit |
| `02_device_indexes.sql` | Device | merchant assignment, heartbeat, current firmware |
| `03_customer_indexes.sql` | Customer | phone hash, fingerprint reuse, blacklist |
| `04_transaction_indexes.sql` | Payments | merchant+time, rrn, partial failed/fraud, all FK joins |
| `05_settlement_refund_chargeback_indexes.sql` | Settlement/Refund/CB | merchant, UTR, open-exception, respond-by queue |
| `06_fraud_support_indexes.sql` | Fraud/Support | open-alert queue, ticket queue, SLA breach |
