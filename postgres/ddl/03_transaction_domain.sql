-- ============================================================
-- 03: Transaction domain (3NF, partitioned)
--
-- transaction_header is RANGE-partitioned by month on created_at.
-- High-churn child tables (details, attempts, auth, capture) FK to
-- the header. Partitioning keeps hot months small and lets old
-- months be detached/archived to ClickHouse cheaply.
-- ============================================================

CREATE TABLE txn.transaction_header (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY,
    transaction_uid    UUID NOT NULL DEFAULT gen_random_uuid(),
    merchant_id        BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    device_id          BIGINT REFERENCES device.device_master(id),
    customer_id        BIGINT REFERENCES customer.customer_master(id),
    rrn                CHAR(12) NOT NULL,
    stan               INTEGER NOT NULL,
    order_id           TEXT,
    payment_method     ref.payment_method NOT NULL,
    channel            TEXT NOT NULL DEFAULT 'pos',         -- pos / ecom / qr / payment_link / autopay
    mcc                CHAR(4) NOT NULL,
    amount             NUMERIC(18,2) NOT NULL CHECK (amount > 0),
    currency           CHAR(3) NOT NULL DEFAULT 'INR',
    state              ref.txn_state NOT NULL DEFAULT 'initiated',
    is_success         BOOLEAN NOT NULL DEFAULT FALSE,
    response_code      TEXT,
    latitude           DOUBLE PRECISION,
    longitude          DOUBLE PRECISION,
    fraud_label        BOOLEAN NOT NULL DEFAULT FALSE,
    fraud_scenario     TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Rolling monthly partitions (3y history + current). Airflow/cron
-- pre-creates the next month; see 90_partition_maint.sql helper.
CREATE TABLE txn.transaction_header_default
    PARTITION OF txn.transaction_header DEFAULT;

DO $$
DECLARE
    start_month DATE := date_trunc('month', CURRENT_DATE) - INTERVAL '36 months';
    m DATE;
BEGIN
    FOR i IN 0..37 LOOP
        m := start_month + (i || ' months')::interval;
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS txn.transaction_header_%s '
            'PARTITION OF txn.transaction_header FOR VALUES FROM (%L) TO (%L)',
            to_char(m, 'YYYYMM'), m, m + INTERVAL '1 month');
    END LOOP;
END $$;

CREATE TABLE txn.transaction_details (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id        BIGINT NOT NULL,
    base_amount           NUMERIC(18,2) NOT NULL,
    tip_amount            NUMERIC(18,2) NOT NULL DEFAULT 0,
    cashback_amount       NUMERIC(18,2) NOT NULL DEFAULT 0,
    convenience_fee       NUMERIC(18,2) NOT NULL DEFAULT 0,
    fx_rate               NUMERIC(12,6) NOT NULL DEFAULT 1,
    is_international       BOOLEAN NOT NULL DEFAULT FALSE,
    is_recurring          BOOLEAN NOT NULL DEFAULT FALSE,
    invoice_number        TEXT,
    narration             TEXT
);

CREATE TABLE txn.payment_instruments (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id  BIGINT NOT NULL,
    instrument_type ref.payment_method NOT NULL,
    card_bin        CHAR(6),
    card_last4      CHAR(4),
    card_hash       TEXT,
    card_network    TEXT REFERENCES ref.card_network(network_code),
    is_tokenized    BOOLEAN DEFAULT FALSE,
    payer_vpa       TEXT,
    wallet_provider TEXT,
    bank_code       TEXT REFERENCES ref.bank(bank_code)
);

CREATE TABLE txn.payment_attempts (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id  BIGINT NOT NULL,
    attempt_no      SMALLINT NOT NULL DEFAULT 1,
    response_code   TEXT,
    response_message TEXT,
    attempted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    latency_ms      INTEGER
);

CREATE TABLE txn.authorization_records (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id  BIGINT NOT NULL,
    auth_code       CHAR(6),
    auth_amount     NUMERIC(18,2) NOT NULL,
    issuer_bank     TEXT REFERENCES ref.bank(bank_code),
    avs_result      TEXT,
    cvv_result      TEXT,
    three_ds_status TEXT,
    auth_latency_ms INTEGER,
    authorized_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE txn.capture_records (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id  BIGINT NOT NULL,
    capture_amount  NUMERIC(18,2) NOT NULL,
    capture_mode    TEXT NOT NULL DEFAULT 'auto',
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE txn.transaction_fees (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id        BIGINT NOT NULL,
    mdr_rate_bps          SMALLINT NOT NULL,
    mdr_amount            NUMERIC(18,4) NOT NULL DEFAULT 0,
    interchange_fee       NUMERIC(18,4) NOT NULL DEFAULT 0,
    network_fee           NUMERIC(18,4) NOT NULL DEFAULT 0,
    net_settlement_amount NUMERIC(18,2) NOT NULL DEFAULT 0
);

CREATE TABLE txn.transaction_taxes (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id  BIGINT NOT NULL,
    gst_on_fees     NUMERIC(18,4) NOT NULL DEFAULT 0,
    gst_rate_pct    NUMERIC(4,2) NOT NULL DEFAULT 18.00
);

CREATE TABLE txn.transaction_status_history (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id  BIGINT NOT NULL,
    from_state      ref.txn_state,
    to_state        ref.txn_state NOT NULL,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE txn.transaction_audit_log (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name  TEXT NOT NULL, row_pk BIGINT NOT NULL, action TEXT NOT NULL,
    changed_by  TEXT NOT NULL DEFAULT current_user, diff JSONB NOT NULL,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Secondary indexes (dominant access paths) -> ../indexes/04_transaction_indexes.sql
