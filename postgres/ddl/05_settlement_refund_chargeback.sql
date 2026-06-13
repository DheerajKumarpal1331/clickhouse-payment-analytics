-- ============================================================
-- 05: Settlement, Refund, Chargeback domains
-- ============================================================

-- ---------- Settlement ----------
CREATE TABLE settlement.settlement_batches (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_code      TEXT NOT NULL UNIQUE,
    cycle_date      DATE NOT NULL,
    settlement_cycle TEXT NOT NULL DEFAULT 'T+1',
    total_merchants INTEGER NOT NULL DEFAULT 0,
    gross_amount    NUMERIC(18,2) NOT NULL DEFAULT 0,
    net_amount      NUMERIC(18,2) NOT NULL DEFAULT 0,
    status          ref.settlement_state NOT NULL DEFAULT 'pending',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE settlement.merchant_settlements (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id          BIGINT NOT NULL REFERENCES settlement.settlement_batches(id),
    merchant_id       BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    txn_count         INTEGER NOT NULL DEFAULT 0,
    gross_amount      NUMERIC(18,2) NOT NULL DEFAULT 0,
    mdr_amount        NUMERIC(18,4) NOT NULL DEFAULT 0,
    gst_amount        NUMERIC(18,4) NOT NULL DEFAULT 0,
    refund_amount     NUMERIC(18,2) NOT NULL DEFAULT 0,
    chargeback_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    rolling_reserve   NUMERIC(18,2) NOT NULL DEFAULT 0,
    net_amount        NUMERIC(18,2) NOT NULL DEFAULT 0,
    status            ref.settlement_state NOT NULL DEFAULT 'pending',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (batch_id, merchant_id)
);

CREATE TABLE settlement.settlement_adjustments (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_settlement_id BIGINT NOT NULL REFERENCES settlement.merchant_settlements(id),
    adjustment_type TEXT NOT NULL,                  -- reserve_release / penalty / correction
    amount          NUMERIC(18,2) NOT NULL,
    reason          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE settlement.bank_transfers (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_settlement_id BIGINT NOT NULL REFERENCES settlement.merchant_settlements(id),
    utr             TEXT,
    ifsc            CHAR(11) NOT NULL,
    account_hash    TEXT NOT NULL,
    amount          NUMERIC(18,2) NOT NULL,
    mode            TEXT NOT NULL DEFAULT 'NEFT',    -- NEFT / RTGS / IMPS / UPI
    status          TEXT NOT NULL DEFAULT 'initiated',
    initiated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE settlement.reconciliation_results (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    batch_id        BIGINT NOT NULL REFERENCES settlement.settlement_batches(id),
    expected_amount NUMERIC(18,2) NOT NULL,
    actual_amount   NUMERIC(18,2) NOT NULL,
    variance        NUMERIC(18,2) GENERATED ALWAYS AS (actual_amount - expected_amount) STORED,
    matched         BOOLEAN NOT NULL DEFAULT FALSE,
    reconciled_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE settlement.settlement_exceptions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_settlement_id BIGINT REFERENCES settlement.merchant_settlements(id),
    exception_type  TEXT NOT NULL,                  -- bank_reject / amount_mismatch / hold
    detail          TEXT,
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Refund ----------
CREATE TABLE refund.refund_requests (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    refund_code     TEXT NOT NULL UNIQUE,
    transaction_id  BIGINT NOT NULL,
    merchant_id     BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    customer_id     BIGINT REFERENCES customer.customer_master(id),
    requested_amount NUMERIC(18,2) NOT NULL CHECK (requested_amount > 0),
    original_amount NUMERIC(18,2) NOT NULL,
    is_partial      BOOLEAN NOT NULL DEFAULT FALSE,
    reason          TEXT NOT NULL,
    initiated_by    TEXT NOT NULL DEFAULT 'merchant',
    status          TEXT NOT NULL DEFAULT 'requested',
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE refund.refund_approvals (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    refund_id       BIGINT NOT NULL REFERENCES refund.refund_requests(id),
    approver        TEXT NOT NULL,
    decision        TEXT NOT NULL,                  -- approved / rejected
    decided_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE refund.refund_transactions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    refund_id       BIGINT NOT NULL REFERENCES refund.refund_requests(id),
    arn             TEXT,
    refund_amount   NUMERIC(18,2) NOT NULL,
    refund_type     TEXT NOT NULL DEFAULT 'online', -- online / offline / reversal
    processed_at    TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'processed'
);

CREATE TABLE refund.refund_status_history (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    refund_id   BIGINT NOT NULL REFERENCES refund.refund_requests(id),
    from_status TEXT, to_status TEXT NOT NULL,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE refund.refund_failures (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    refund_id   BIGINT NOT NULL REFERENCES refund.refund_requests(id),
    failure_code TEXT NOT NULL,
    failure_reason TEXT,
    failed_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------- Chargeback ----------
CREATE TABLE chargeback.chargeback_cases (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_code       TEXT NOT NULL UNIQUE,
    transaction_id  BIGINT NOT NULL,
    merchant_id     BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    network         TEXT,
    reason_code     TEXT NOT NULL,
    reason_category TEXT NOT NULL,                  -- fraud / service / processing
    stage           TEXT NOT NULL DEFAULT 'first_chargeback',
    status          TEXT NOT NULL DEFAULT 'open',
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    respond_by      DATE NOT NULL
);

CREATE TABLE chargeback.chargeback_evidence (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_id         BIGINT NOT NULL REFERENCES chargeback.chargeback_cases(id),
    evidence_type   TEXT NOT NULL,
    storage_key     TEXT NOT NULL,
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chargeback.chargeback_financials (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_id         BIGINT NOT NULL UNIQUE REFERENCES chargeback.chargeback_cases(id),
    dispute_amount  NUMERIC(18,2) NOT NULL,
    liability       TEXT,                           -- merchant / issuer / acquirer
    recovered_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    write_off_amount NUMERIC(18,2) NOT NULL DEFAULT 0
);

CREATE TABLE chargeback.chargeback_resolution (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_id         BIGINT NOT NULL UNIQUE REFERENCES chargeback.chargeback_cases(id),
    outcome         TEXT NOT NULL,                  -- won / lost / accepted
    resolved_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_by     TEXT
);

CREATE TABLE chargeback.chargeback_timeline (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_id     BIGINT NOT NULL REFERENCES chargeback.chargeback_cases(id),
    event       TEXT NOT NULL,
    event_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Secondary indexes -> ../indexes/05_settlement_refund_chargeback_indexes.sql
