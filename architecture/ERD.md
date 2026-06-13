# Entity Relationship Diagram (ERD)

> The OLTP model is ~80 tables across 10 schemas — too dense for one diagram, so
> it's split by domain (the standard approach for a large normalized schema).
> Each diagram shows the hub table, its key satellites, and cross-domain links.
> The ClickHouse star schema follows at the end. Full columns are in
> [`../postgres/ddl/`](../postgres/ddl) and the data dictionary.

Legend: `PK` primary key · `FK` foreign key · `UK` unique key.

---

## 1. Reference / master data (`ref`)

```mermaid
erDiagram
    merchant_category   ||--o{ MERCHANT_MASTER : classifies
    card_network        ||--o{ card_bin_master : "owns BIN range"
    bank                ||--o{ card_bin_master : issues
    location            ||--o{ MERCHANT_ADDR : locates

    merchant_category { string mcc PK  string segment  float risk_weight }
    card_network      { string network_code PK  float interchange_share }
    bank              { string bank_code PK  bool is_issuer  bool is_acquirer }
    card_bin_master   { string bin PK  string network_code FK  string issuer_bank FK  string card_type }
    location          { bigint location_id PK  string city  string state  string pincode }
```

---

## 2. Merchant domain

```mermaid
erDiagram
    MERCHANT_MASTER ||--|| merchant_kyc : has
    MERCHANT_MASTER ||--o{ merchant_addresses : has
    MERCHANT_MASTER ||--o{ merchant_contacts : has
    MERCHANT_MASTER ||--o{ merchant_bank_accounts : has
    MERCHANT_MASTER ||--o{ merchant_users : has
    MERCHANT_MASTER ||--o{ merchant_documents : has
    MERCHANT_MASTER ||--o{ merchant_pricing : "priced by (time-versioned)"
    MERCHANT_MASTER ||--|| merchant_risk_profiles : scored
    MERCHANT_MASTER ||--|| merchant_settlement_configuration : configured
    MERCHANT_MASTER ||--o{ merchant_status_history : tracks
    merchant_bank_accounts ||--o| merchant_settlement_configuration : "default account"

    MERCHANT_MASTER {
        bigint id PK
        string merchant_code UK
        string legal_name
        string dba_name
        string mcc FK
        enum   status
        date   onboarded_date
    }
    merchant_kyc            { bigint id PK  bigint merchant_id FK  string pan_hash  enum kyc_status }
    merchant_pricing        { bigint id PK  bigint merchant_id FK  int mdr_card_credit_bps  date effective_from }
    merchant_risk_profiles  { bigint id PK  bigint merchant_id FK  enum risk_tier  int velocity_limit_per_day }
    merchant_bank_accounts  { bigint id PK  bigint merchant_id FK  string account_hash  string ifsc }
```

---

## 3. Device & Customer domains

```mermaid
erDiagram
    DEVICE_MASTER ||--|| device_inventory : "stock status"
    DEVICE_MASTER ||--o{ device_assignment : "assigned to merchant"
    DEVICE_MASTER ||--|| device_activation : activated
    DEVICE_MASTER ||--o{ device_firmware : versions
    DEVICE_MASTER ||--o{ device_health : "health samples"
    DEVICE_MASTER ||--o{ device_network_status : connectivity
    MERCHANT_MASTER ||--o{ device_assignment : owns

    CUSTOMER_MASTER ||--o{ customer_devices : has
    CUSTOMER_MASTER ||--o{ customer_addresses : has
    CUSTOMER_MASTER ||--|| customer_risk_profiles : scored
    CUSTOMER_MASTER ||--|| customer_payment_preferences : prefers
    CUSTOMER_MASTER ||--o{ customer_consent : grants

    DEVICE_MASTER   { bigint id PK  string device_code UK  string terminal_id  string terminal_type }
    device_assignment { bigint id PK  bigint device_id FK  bigint merchant_id FK  timestamp released_at }
    CUSTOMER_MASTER { bigint id PK  string customer_code UK  string phone_hash  enum status }
    customer_risk_profiles { bigint id PK  bigint customer_id FK  enum risk_profile  bool is_blacklisted }
```

---

## 4. Transaction domain (hub of the platform)

```mermaid
erDiagram
    TRANSACTION_HEADER ||--|| transaction_details : has
    TRANSACTION_HEADER ||--o{ payment_attempts : has
    TRANSACTION_HEADER ||--|| payment_instruments : "paid with"
    TRANSACTION_HEADER ||--o| authorization_records : authorized
    TRANSACTION_HEADER ||--o| capture_records : captured
    TRANSACTION_HEADER ||--|| transaction_fees : "fees on"
    TRANSACTION_HEADER ||--|| transaction_taxes : "taxed by"
    TRANSACTION_HEADER ||--o{ transaction_status_history : tracks
    TRANSACTION_HEADER ||--o| upi_transactions : "if UPI"
    TRANSACTION_HEADER ||--o| card_transactions : "if card"
    MERCHANT_MASTER ||--o{ TRANSACTION_HEADER : accepts
    CUSTOMER_MASTER ||--o{ TRANSACTION_HEADER : makes
    DEVICE_MASTER   ||--o{ TRANSACTION_HEADER : "captured on"

    TRANSACTION_HEADER {
        bigint id PK
        uuid   transaction_uid
        bigint merchant_id FK
        bigint device_id FK
        bigint customer_id FK
        string rrn
        enum   payment_method
        numeric amount
        enum   state
        bool   is_success
        timestamp created_at "partition key"
    }
    transaction_fees { bigint id PK  bigint transaction_id FK  int mdr_rate_bps  numeric mdr_amount  numeric net_settlement_amount }
    card_transactions { bigint id PK  bigint transaction_id FK  string card_bin FK  string pos_entry_mode }
    upi_transactions  { bigint id PK  bigint transaction_id FK  string upi_txn_ref  string upi_flow }
```

---

## 5. Settlement / Refund / Chargeback domains

```mermaid
erDiagram
    settlement_batches ||--o{ merchant_settlements : contains
    merchant_settlements ||--o{ settlement_adjustments : "adjusted by"
    merchant_settlements ||--o{ bank_transfers : "paid via"
    merchant_settlements ||--o{ settlement_exceptions : "may raise"
    settlement_batches ||--o{ reconciliation_results : reconciled
    MERCHANT_MASTER ||--o{ merchant_settlements : "settled to"

    refund_requests ||--o{ refund_approvals : "approved by"
    refund_requests ||--o| refund_transactions : "processed as"
    refund_requests ||--o{ refund_status_history : tracks
    refund_requests ||--o{ refund_failures : "may fail"
    TRANSACTION_HEADER ||--o{ refund_requests : "refunded by"

    chargeback_cases ||--o{ chargeback_evidence : has
    chargeback_cases ||--|| chargeback_financials : "valued by"
    chargeback_cases ||--o| chargeback_resolution : resolved
    chargeback_cases ||--o{ chargeback_timeline : tracks
    TRANSACTION_HEADER ||--o{ chargeback_cases : disputed

    merchant_settlements { bigint id PK  bigint batch_id FK  bigint merchant_id FK  numeric net_amount  enum status }
    refund_requests      { bigint id PK  bigint transaction_id FK  numeric requested_amount  string status }
    chargeback_cases     { bigint id PK  bigint transaction_id FK  string reason_code  string status  date respond_by }
```

---

## 6. Fraud & Support domains

```mermaid
erDiagram
    fraud_rules   ||--o{ fraud_alerts : triggers
    fraud_scores  ||--o{ fraud_alerts : escalates
    fraud_alerts  ||--o| fraud_cases : "grouped into"
    fraud_cases   ||--o{ fraud_investigations : "worked in"
    MERCHANT_MASTER ||--o{ fraud_cases : "subject of"
    MERCHANT_MASTER ||--o| merchant_blacklists : "may be on"
    CUSTOMER_MASTER ||--o| customer_blacklists : "may be on"

    support_tickets ||--o{ ticket_comments : has
    support_tickets ||--o{ ticket_status_history : tracks
    support_tickets ||--o{ ticket_escalations : "escalated via"
    support_tickets ||--|| sla_tracking : "measured by"
    MERCHANT_MASTER ||--o{ support_tickets : raises

    fraud_scores    { bigint id PK  bigint transaction_id FK  string model_version  numeric score  enum risk_level }
    fraud_cases     { bigint id PK  string case_code UK  string fraud_type  numeric estimated_loss  string status }
    support_tickets { bigint id PK  string ticket_code UK  string category  string priority  string status }
    sla_tracking    { bigint id PK  bigint ticket_id FK  int sla_target_mins  bool breached }
```

---

## 7. ClickHouse star schema (OLAP)

The analytical model denormalizes the OLTP entities into wide fact tables
surrounded by conformed dimensions. Facts share `merchant_id` / `event_time`
grain; MVs roll them up.

```mermaid
erDiagram
    dim_merchants       ||--o{ fact_transactions : describes
    dim_customers       ||--o{ fact_transactions : describes
    dim_devices         ||--o{ fact_transactions : describes
    dim_dates           ||--o{ fact_transactions : "calendar"
    dim_payment_methods ||--o{ fact_transactions : classifies
    dim_products        ||--o{ fact_transactions : "MCC rollup"
    dim_risk_levels     ||--o{ fact_fraud_events : bands

    fact_transactions ||--o{ fact_refunds : "refunded by"
    fact_transactions ||--o{ fact_chargebacks : "disputed by"
    fact_transactions ||--o{ fact_fraud_events : scored
    fact_transactions ||--o{ fact_settlements : "settled in"

    fact_transactions {
        string transaction_id
        string merchant_id "ORDER BY"
        datetime event_time "ORDER BY / PARTITION"
        decimal amount
        string payment_method
        uint8  is_success
        uint8  fraud_label
        string card_hash "~95 cols total"
    }
    dim_merchants { string merchant_id PK  string mcc  string risk_tier  string city }
    fact_settlements { string settlement_batch_id  string merchant_id  date cycle_date  decimal net_amount  uint32 tat_minutes }
    fact_fraud_events { string event_id  string transaction_id  float score  string risk_level }
```

**MV rollups (not entities, but derived tables):** `agg_merchant_daily/hourly/
monthly`, `agg_velocity_5m`, `agg_fraud_features`, `agg_settlement_perf`,
`agg_device_health`, `agg_revenue_daily` — each fed by a `mv_*` and read via a
finalized `v_*` view.
