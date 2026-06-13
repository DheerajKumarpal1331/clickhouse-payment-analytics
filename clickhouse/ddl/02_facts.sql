-- ============================================================
-- 02: Fact tables
--
-- fact_transactions is the wide processor record (~90 cols: ISO 8583, EMV,
-- 3DS, full fee breakdown, settlement linkage, device/network telemetry, geo).
-- The Kafka consumer inserts JSONEachRow with skip-unknown + null-as-default,
-- so a narrow OLTP-CDC event fills the core and defaults the rest, while the
-- generator's wide payload fills everything. Column names match both the
-- event contracts (kafka/schemas) and the generator (data_generator/enrichment).
--
-- All facts: MergeTree, time-partitioned, ORDER BY (merchant_id, time) — the
-- dominant dashboard access path. Money is Decimal (never float).
-- ============================================================

CREATE TABLE IF NOT EXISTS payments.fact_transactions
(
    -- identifiers
    transaction_id        String,
    rrn                   String DEFAULT '',
    stan                  UInt32 DEFAULT 0,
    auth_code             String DEFAULT '',
    order_id              String DEFAULT '',
    invoice_number        String DEFAULT '',
    parent_transaction_id String DEFAULT '',
    gateway_txn_id        String DEFAULT '',
    acquirer_txn_id       String DEFAULT '',
    network_txn_id        String DEFAULT '',
    upi_txn_ref           String DEFAULT '',
    trace_id              String DEFAULT '',
    -- parties
    merchant_id           LowCardinality(String),
    sub_merchant_id       String DEFAULT '',
    store_id              LowCardinality(String) DEFAULT '',
    device_id             String DEFAULT '',
    terminal_id           String DEFAULT '',
    customer_id           String DEFAULT '',
    aggregator_id         LowCardinality(String) DEFAULT '',
    acquirer_id           LowCardinality(String) DEFAULT '',
    acquirer_bank         LowCardinality(String) DEFAULT '',
    issuer_bank           LowCardinality(String) DEFAULT '',
    issuer_country        LowCardinality(String) DEFAULT 'IN',
    payer_vpa             String DEFAULT '',
    payee_vpa             String DEFAULT '',
    -- timestamps
    event_time            DateTime,
    event_date            Date MATERIALIZED toDate(event_time),
    auth_time             DateTime64(3) DEFAULT toDateTime64(0, 3),
    capture_time          Nullable(DateTime64(3)),
    settlement_time       Nullable(DateTime),
    device_time           DateTime64(3) DEFAULT toDateTime64(0, 3),
    auth_latency_ms       UInt32 DEFAULT 0,
    -- amounts & fees
    amount                Decimal(18, 2),
    currency              LowCardinality(String) DEFAULT 'INR',
    base_amount           Decimal(18, 2) DEFAULT 0,
    tip_amount            Decimal(18, 2) DEFAULT 0,
    cashback_amount       Decimal(18, 2) DEFAULT 0,
    tax_amount            Decimal(18, 2) DEFAULT 0,
    convenience_fee       Decimal(18, 2) DEFAULT 0,
    fx_rate               Decimal(12, 6) DEFAULT 1,
    mdr_rate_bps          UInt16 DEFAULT 0,
    mdr_amount            Decimal(18, 4) DEFAULT 0,
    interchange_fee       Decimal(18, 4) DEFAULT 0,
    network_fee           Decimal(18, 4) DEFAULT 0,
    gst_on_fees           Decimal(18, 4) DEFAULT 0,
    net_settlement_amount Decimal(18, 2) DEFAULT 0,
    -- instrument: card
    payment_method        LowCardinality(String),
    card_network          LowCardinality(String) DEFAULT '',
    card_type             LowCardinality(String) DEFAULT '',
    card_bin              String DEFAULT '',
    card_last4            String DEFAULT '',
    card_hash             String DEFAULT '',
    is_tokenized          UInt8 DEFAULT 0,
    token_requestor_id    String DEFAULT '',
    is_international      UInt8 DEFAULT 0,
    card_issuer_country   LowCardinality(String) DEFAULT 'IN',
    emi_flag              UInt8 DEFAULT 0,
    emi_tenure_months     UInt8 DEFAULT 0,
    -- instrument: upi / wallet / netbanking
    upi_provider          LowCardinality(String) DEFAULT '',
    upi_flow              LowCardinality(String) DEFAULT '',
    wallet_provider       LowCardinality(String) DEFAULT '',
    netbanking_bank       LowCardinality(String) DEFAULT '',
    -- entry mode / EMV
    pos_entry_mode        LowCardinality(String) DEFAULT '',
    emv_aid               String DEFAULT '',
    emv_tvr               String DEFAULT '',
    emv_tsi               String DEFAULT '',
    cvm_method            LowCardinality(String) DEFAULT '',
    fallback_flag         UInt8 DEFAULT 0,
    -- authorization result
    response_code         LowCardinality(String) DEFAULT '',
    response_message      LowCardinality(String) DEFAULT '',
    is_success            UInt8,
    avs_result            LowCardinality(String) DEFAULT '',
    cvv_result            LowCardinality(String) DEFAULT '',
    three_ds_version      LowCardinality(String) DEFAULT '',
    three_ds_eci          LowCardinality(String) DEFAULT '',
    three_ds_status       LowCardinality(String) DEFAULT '',
    retry_count           UInt8 DEFAULT 0,
    capture_mode          LowCardinality(String) DEFAULT 'auto',
    -- settlement
    settlement_status     LowCardinality(String) DEFAULT 'pending',
    settlement_batch_id   String DEFAULT '',
    settlement_cycle      LowCardinality(String) DEFAULT 'T+1',
    settlement_utr        String DEFAULT '',
    -- channel & catalog
    channel               LowCardinality(String) DEFAULT '',
    mcc                   LowCardinality(String) DEFAULT '',
    product_code          LowCardinality(String) DEFAULT '',
    is_recurring          UInt8 DEFAULT 0,
    -- device / network telemetry
    firmware_version      LowCardinality(String) DEFAULT '',
    app_version           LowCardinality(String) DEFAULT '',
    sdk_version           LowCardinality(String) DEFAULT '',
    network_type          LowCardinality(String) DEFAULT '',
    sim_operator          LowCardinality(String) DEFAULT '',
    ip_address            String DEFAULT '',
    device_fingerprint    String DEFAULT '',
    user_agent            String DEFAULT '' CODEC(ZSTD(3)),
    battery_level         UInt8 DEFAULT 0,
    -- geo
    latitude              Float64 DEFAULT 0,
    longitude             Float64 DEFAULT 0,
    geo_accuracy_m        UInt16 DEFAULT 0,
    city                  LowCardinality(String) DEFAULT '',
    state                 LowCardinality(String) DEFAULT '',
    pincode               String DEFAULT '',
    country               LowCardinality(String) DEFAULT 'IN',
    -- risk / labels / lineage
    gateway_risk_score    Float32 DEFAULT 0,
    fraud_label           UInt8 DEFAULT 0,
    fraud_scenario        LowCardinality(String) DEFAULT '',
    schema_version        UInt8 DEFAULT 2,
    source_system         LowCardinality(String) DEFAULT 'switch',
    ingested_at           DateTime DEFAULT now(),

    INDEX idx_txn_id   transaction_id TYPE bloom_filter(0.01) GRANULARITY 4,
    INDEX idx_rrn      rrn            TYPE bloom_filter(0.01) GRANULARITY 4,
    INDEX idx_customer customer_id    TYPE bloom_filter(0.01) GRANULARITY 4,
    INDEX idx_device   device_id      TYPE bloom_filter(0.01) GRANULARITY 4,
    INDEX idx_card     card_hash      TYPE bloom_filter(0.01) GRANULARITY 4,
    INDEX idx_amount   amount         TYPE minmax GRANULARITY 4
)
ENGINE = MergeTree
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (merchant_id, event_time, transaction_id)
TTL event_time + INTERVAL 18 MONTH
SETTINGS index_granularity = 8192;

-- ============================================================
CREATE TABLE IF NOT EXISTS payments.fact_refunds
(
    refund_id      String,
    transaction_id String DEFAULT '',
    rrn            String DEFAULT '',
    merchant_id    LowCardinality(String),
    customer_id    String DEFAULT '',
    event_time     DateTime,
    amount         Decimal(18, 2),
    original_amount Decimal(18, 2) DEFAULT 0,
    is_partial     UInt8 DEFAULT 0,
    refund_type    LowCardinality(String) DEFAULT 'online',
    reason         LowCardinality(String) DEFAULT '',
    initiated_by   LowCardinality(String) DEFAULT '',
    status         LowCardinality(String) DEFAULT 'processed',
    is_abusive     UInt8 DEFAULT 0,
    ingested_at    DateTime DEFAULT now()
)
ENGINE = MergeTree PARTITION BY toYYYYMM(event_time) ORDER BY (merchant_id, event_time);

CREATE TABLE IF NOT EXISTS payments.fact_chargebacks
(
    chargeback_id   String,
    transaction_id  String DEFAULT '',
    rrn             String DEFAULT '',
    merchant_id     LowCardinality(String),
    customer_id     String DEFAULT '',
    event_time      DateTime,
    amount          Decimal(18, 2) DEFAULT 0,
    reason_code     LowCardinality(String) DEFAULT '',
    reason_category LowCardinality(String) DEFAULT '',
    network         LowCardinality(String) DEFAULT '',
    stage           LowCardinality(String) DEFAULT 'first_chargeback',
    status          LowCardinality(String) DEFAULT 'open',
    liability       LowCardinality(String) DEFAULT '',
    ingested_at     DateTime DEFAULT now()
)
ENGINE = MergeTree PARTITION BY toYYYYMM(event_time) ORDER BY (merchant_id, event_time);

CREATE TABLE IF NOT EXISTS payments.fact_settlements
(
    settlement_batch_id String,
    merchant_id         LowCardinality(String),
    cycle_date          Date,
    settlement_cycle    LowCardinality(String) DEFAULT 'T+1',
    txn_count           UInt32 DEFAULT 0,
    gross_amount        Decimal(18, 2) DEFAULT 0,
    refund_amount       Decimal(18, 2) DEFAULT 0,
    chargeback_amount   Decimal(18, 2) DEFAULT 0,
    mdr_amount          Decimal(18, 4) DEFAULT 0,
    gst_amount          Decimal(18, 4) DEFAULT 0,
    net_amount          Decimal(18, 2),
    status              LowCardinality(String) DEFAULT 'pending',
    tat_minutes         UInt32 DEFAULT 0,
    utr                 String DEFAULT '',
    ingested_at         DateTime DEFAULT now()
)
ENGINE = MergeTree PARTITION BY toYYYYMM(cycle_date) ORDER BY (merchant_id, cycle_date);

CREATE TABLE IF NOT EXISTS payments.fact_support_events
(
    ticket_id       String,
    merchant_id     LowCardinality(String) DEFAULT '',
    customer_id     String DEFAULT '',
    event_time      DateTime,
    category        LowCardinality(String) DEFAULT '',
    priority        LowCardinality(String) DEFAULT '',
    status          LowCardinality(String) DEFAULT '',
    channel         LowCardinality(String) DEFAULT '',
    resolution_mins UInt32 DEFAULT 0,
    sla_breached    UInt8 DEFAULT 0,
    escalated       UInt8 DEFAULT 0,
    ingested_at     DateTime DEFAULT now()
)
ENGINE = MergeTree PARTITION BY toYYYYMM(event_time) ORDER BY (merchant_id, event_time);

CREATE TABLE IF NOT EXISTS payments.fact_device_events
(
    device_id     String,
    merchant_id   LowCardinality(String) DEFAULT '',
    event_time    DateTime,
    terminal_type LowCardinality(String) DEFAULT '',
    status        LowCardinality(String) DEFAULT '',
    network_type  LowCardinality(String) DEFAULT '',
    battery_level UInt8 DEFAULT 0,
    health_score  Float32 DEFAULT 1,
    event_type    LowCardinality(String) DEFAULT 'heartbeat',
    ingested_at   DateTime DEFAULT now()
)
ENGINE = MergeTree PARTITION BY toYYYYMM(event_time) ORDER BY (device_id, event_time);

CREATE TABLE IF NOT EXISTS payments.fact_fraud_events
(
    event_id      String,
    transaction_id String DEFAULT '',
    merchant_id   LowCardinality(String),
    scored_at     DateTime,
    score         Float32,
    risk_level    LowCardinality(String) DEFAULT '',
    model_version LowCardinality(String) DEFAULT '',
    reason_codes  Array(LowCardinality(String)) DEFAULT [],
    latency_ms    Float32 DEFAULT 0,
    ingested_at   DateTime DEFAULT now()
)
ENGINE = MergeTree PARTITION BY toYYYYMM(scored_at) ORDER BY (merchant_id, scored_at)
TTL scored_at + INTERVAL 6 MONTH;
