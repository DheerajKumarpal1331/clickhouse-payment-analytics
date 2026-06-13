# Low-Level Design (LLD)

> Component-by-component implementation detail: schemas, partitioning, Kafka
> topic configs, materialized-view strategy, feature-store mechanics, and API
> contracts. Pairs with [`HLD.md`](HLD.md) (the why) and [`ERD.md`](ERD.md) (the
> entities).

---

## 1. OLTP — PostgreSQL

**Schema-per-domain** (`merchant`, `device`, `customer`, `txn`, `settlement`,
`refund`, `chargeback`, `fraud`, `support`, `ref`). DDL in
[`../postgres/ddl/`](../postgres/ddl).

### Keys & money
- Surrogate `BIGINT GENERATED ALWAYS AS IDENTITY` PKs; natural keys
  (`merchant_code`, `rrn`) are `UNIQUE`.
- All money is `NUMERIC(18,2)` (or `(18,4)` for fee precision) — never float.

### Partitioning
`txn.transaction_header` is `RANGE` partitioned by month on `created_at`
(38 historical + current + default). Child tables (`transaction_details`,
`payment_attempts`, `authorization_records`, `capture_records`,
`transaction_fees`) reference the header by `transaction_id`. Old months can be
detached and archived to ClickHouse.

### Integrity beyond FKs
- Partial unique indexes: one primary settlement account per merchant, one live
  device assignment at a time.
- GiST `EXCLUDE` on `merchant_pricing` forbids overlapping price windows.
- Generated column: `reconciliation_results.variance = actual − expected`.

### Triggers & procedures ([`07_triggers_functions.sql`](../postgres/ddl/07_triggers_functions.sql))
- `ref.touch_updated_at()` — maintains `updated_at`.
- `ref.audit_row(log_table)` — generic JSONB diff into `*_audit_log`.
- `merchant.log_status_change()` / `txn.log_state_change()` — append to history.
- `merchant.sp_onboard_merchant()` — atomic 5-table onboarding.
- `txn.sp_compute_fees()` — MDR + interchange + GST + net at capture.

---

## 2. Streaming — Kafka

8 topics, keyed for ordering and co-partitioning:

| Topic | Key | Schema (`kafka/schemas/events.py`) | CH sink |
|---|---|---|---|
| `transaction_events` | merchant_id | `TransactionEvent` | `fact_transactions` |
| `refund_events` | merchant_id | `RefundEvent` | `fact_refunds` |
| `chargeback_events` | merchant_id | `ChargebackEvent` | `fact_chargebacks` |
| `settlement_events` | merchant_id | `SettlementEvent` | `fact_settlements` |
| `fraud_events` | merchant_id | `FraudEvent` | `fact_fraud_events` |
| `support_events` | merchant_id | `SupportEvent` | `fact_support_events` |
| `merchant_events` | merchant_id | `MerchantEvent` | `dim_merchants` + `fact_merchant_events` |
| `device_events` | device_id | `DeviceEvent` | `fact_device_events` |

### Reliability
- **Producer:** `acks=all`, `linger.ms=20`, `lz4` compression, idempotent.
- **Validation:** Pydantic models with `extra='allow'` — the load-bearing core
  is validated strictly, the long enrichment tail passes through so schema
  evolution never stalls ingest.
- **DLQ:** events failing validation/insert are written to
  `payments.dead_letter_events` (topic, raw payload, error) with bounded retry.
- **Keying by merchant_id** preserves per-merchant order and co-locates a
  merchant's events on one partition for velocity features.

---

## 3. OLAP — ClickHouse

DDL in [`../clickhouse/ddl/`](../clickhouse/ddl). Validated end-to-end against
ClickHouse 24.3.

### Engines by purpose
| Engine | Used for | Why |
|---|---|---|
| `MergeTree` | fact tables | append-heavy, time-partitioned |
| `ReplacingMergeTree(updated_at)` | dimensions, online features | latest-row-wins upserts |
| `AggregatingMergeTree` | MV targets | mergeable partial aggregates |
| `TinyLog` | tiny static dims (`dim_risk_levels`) | trivial size |

### `fact_transactions` (the wide one — ~95 cols)
- `PARTITION BY toYYYYMMDD(event_time)`, `ORDER BY (merchant_id, event_time, transaction_id)`.
- `event_date` is `MATERIALIZED`; `ingested_at` defaulted.
- Skip indexes: `bloom_filter` on `transaction_id`/`rrn`/`customer_id`/`device_id`/`card_hash`,
  `minmax` on `amount`.
- `LowCardinality(String)` for all enums/categoricals; `ZSTD(3)` on `user_agent`.
- TTL 18 months.

### Materialized-view strategy
MVs write `-State` partial aggregates; **dashboards must query the finalized
`v_*` views** that apply `-Merge`. Never `SELECT` the `agg_*` table raw.

| MV | Target (AggregatingMergeTree) | Finalized view |
|---|---|---|
| `mv_merchant_daily/hourly/monthly` | `agg_merchant_*` | `v_merchant_daily`, `v_merchant_monthly` |
| `mv_velocity_customer/device` | `agg_velocity_5m` | (read directly with `-Merge`) |
| `mv_fraud_features` | `agg_fraud_features` | `v_fraud_features` |
| `mv_success_metrics` | `agg_success_metrics` | `v_hourly_success` |
| `mv_settlement_perf` | `agg_settlement_perf` | — |
| `mv_device_health` | `agg_device_health` | — |
| `mv_revenue_daily` | `agg_revenue_daily` | `v_revenue_daily` |

### Dimensions (star schema)
`dim_merchants`, `dim_customers`, `dim_devices`, `dim_dates` (pre-generated
2022–2027), `dim_locations`, `dim_payment_methods`, `dim_risk_levels`,
`dim_products`.

---

## 4. Feature store

Two physical tables backed by ClickHouse aggregates:

- **Offline** (`payments.offline_features`, MergeTree): append-only, carries
  `feature_time`. Training joins use **ASOF JOIN ... feature_time <= label_time**
  for point-in-time correctness (no label leakage).
- **Online** (`payments.online_features`, ReplacingMergeTree): latest row per
  `(entity_type, entity_id)`, read with `FINAL` on a single key (one-key lookup
  is sub-ms). TTL 30 days.

Feature families: merchant (velocity, success/refund/chargeback rate), customer
(spend, frequency, risk), device (health, velocity, failure), fraud (geo/device/
merchant velocity, amount anomalies). Computed by Airflow feature-gen DAGs from
the `agg_*`/`mv_*` rollups.

---

## 5. ML / MLOps

- Models: `XGBoost`, `LightGBM`, `RandomForest` (scikit-learn).
- Tracking: **MLflow** logs params, metrics (Precision, Recall, F1, ROC-AUC,
  PR-AUC), and the model artifact; best run is promoted in the **model registry**.
- Explainability: **SHAP** values surfaced as `reason_codes` and on the dashboard.
- Class imbalance (~0.4% fraud): handled via `scale_pos_weight` / class weights
  and PR-AUC as the primary selection metric.
- Retraining: weekly Airflow DAG pulls fresh PIT features + confirmed labels
  (fraud cases + chargebacks), retrains, evaluates against the champion, promotes
  on improvement.

---

## 6. Fraud scoring API (FastAPI)

| Endpoint | Method | Contract |
|---|---|---|
| `/score` | POST | in: transaction event → out: `{score, risk_level, reason_codes, model_version, latency_ms}` |
| `/features` | GET | online features for an entity (debug/inspection) |
| `/model-info` | GET | active model version, metrics, trained-at |
| `/health` | GET | liveness + model-loaded + CH reachable |

Path: rules pre-check → online feature fetch (single-key CH read) →
`predict_proba` → band via `dim_risk_levels` → **async** write to
`fraud_scores`/`fact_fraud_events`. Model held in-process; features cached with a
short TTL. Budget p99 < 100 ms.

---

## 7. Orchestration — Airflow DAGs

`merchant_etl`, `transaction_etl`, `settlement_etl`, `refund_etl`,
`feature_engineering`, `fraud_feature_generation`, `model_training`,
`data_quality_validation`, `data_backfill`, `monitoring`. Each: idempotent tasks,
retries with backoff, DQ gates that fail the run on threshold breach, and
`fact_*`/`dq_results` write-back.

---

## 8. Observability

- App metrics via `/metrics` (Prometheus client): request latency histograms,
  score latency, consumer lag, insert rates.
- Exporters: kafka-exporter, clickhouse `/metrics`, postgres-exporter.
- Grafana dashboards + alert rules: Kafka lag > threshold, API p99 > 100 ms, CH
  query time, Airflow task failures, data-freshness gap.

---

## 9. Data-quality framework

Checks (`data_quality/`): null validation, duplicate detection (by natural key),
schema validation, outlier detection (amount z-score), freshness (max
`ingested_at` lag). Results → `payments.dq_results` (pass/warn/fail + metric +
threshold) → scorecard on the Operations dashboard.
