-- ============================================================
-- 01: Merchant domain (3NF)
-- merchant_master is the hub; satellite tables hold KYC, addresses,
-- contacts, banking, users, documents, pricing, risk, settlement
-- config, status history and audit. All FK -> merchant_master.id.
-- ============================================================

CREATE TABLE merchant.merchant_master (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_code        TEXT NOT NULL UNIQUE,                 -- external id e.g. M3F9A1B2C0
    legal_name           TEXT NOT NULL,
    dba_name             TEXT NOT NULL,
    mcc                  CHAR(4) NOT NULL REFERENCES ref.merchant_category(mcc),
    entity_type          TEXT NOT NULL DEFAULT 'proprietorship',
    category             TEXT NOT NULL DEFAULT 'offline',      -- offline / online / omni
    parent_merchant_id   BIGINT REFERENCES merchant.merchant_master(id),
    sales_channel        TEXT NOT NULL DEFAULT 'field',
    relationship_manager TEXT,
    status               ref.lifecycle_status NOT NULL DEFAULT 'pending',
    onboarded_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    activation_date      DATE,
    churn_date           DATE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (churn_date IS NULL OR churn_date >= onboarded_date)
);
COMMENT ON TABLE merchant.merchant_master IS
    'Master merchant record. One row per onboarded business. Hub of merchant domain.';

CREATE TABLE merchant.merchant_kyc (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id      BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    pan_hash         TEXT NOT NULL,                  -- SHA-256, never raw PII
    gstin_masked     TEXT,
    aadhaar_hash     TEXT,
    cin              TEXT,                            -- company id number for pvt ltd
    kyc_status       ref.kyc_status NOT NULL DEFAULT 'pending',
    risk_flag        BOOLEAN NOT NULL DEFAULT FALSE,
    verified_by      TEXT,
    verified_at      TIMESTAMPTZ,
    expires_at       DATE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (merchant_id)
);

CREATE TABLE merchant.merchant_addresses (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id   BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    address_type  TEXT NOT NULL DEFAULT 'registered', -- registered / operating / billing
    line1         TEXT NOT NULL,
    line2         TEXT,
    location_id   BIGINT REFERENCES ref.location(location_id),
    is_primary    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (merchant_id, address_type)
);

CREATE TABLE merchant.merchant_contacts (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id   BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    contact_type  TEXT NOT NULL DEFAULT 'primary',
    name          TEXT NOT NULL,
    phone_hash    TEXT NOT NULL,
    email_hash    TEXT,
    is_primary    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE merchant.merchant_bank_accounts (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id        BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    account_hash       TEXT NOT NULL,
    ifsc               CHAR(11) NOT NULL,
    bank_code          TEXT REFERENCES ref.bank(bank_code),
    account_type       TEXT NOT NULL DEFAULT 'current',
    is_primary         BOOLEAN NOT NULL DEFAULT TRUE,
    penny_drop_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- exactly one primary settlement account per merchant
CREATE UNIQUE INDEX uq_merchant_primary_bank
    ON merchant.merchant_bank_accounts (merchant_id) WHERE is_primary;

CREATE TABLE merchant.merchant_users (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id   BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    username      TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'staff',     -- owner / admin / staff / accountant
    phone_hash    TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (merchant_id, username)
);

CREATE TABLE merchant.merchant_documents (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id   BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    doc_type      TEXT NOT NULL,                     -- pan / gst / bank_proof / shop_license
    storage_key   TEXT NOT NULL,                     -- object-store pointer (no blob in OLTP)
    status        TEXT NOT NULL DEFAULT 'uploaded',  -- uploaded / verified / rejected
    uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE merchant.merchant_pricing (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id          BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    pricing_plan         TEXT NOT NULL DEFAULT 'standard',
    mdr_card_credit_bps  SMALLINT NOT NULL DEFAULT 180,
    mdr_card_debit_bps   SMALLINT NOT NULL DEFAULT 40,
    mdr_upi_bps          SMALLINT NOT NULL DEFAULT 0,
    mdr_wallet_bps       SMALLINT NOT NULL DEFAULT 150,
    mdr_emi_bps          SMALLINT NOT NULL DEFAULT 220,
    fixed_fee_paise      INTEGER NOT NULL DEFAULT 0,
    effective_from       DATE NOT NULL DEFAULT CURRENT_DATE,
    effective_to         DATE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (effective_to IS NULL OR effective_to > effective_from)
);
-- no overlapping pricing windows per merchant
ALTER TABLE merchant.merchant_pricing
    ADD CONSTRAINT no_overlap_pricing EXCLUDE USING gist (
        merchant_id WITH =,
        daterange(effective_from, COALESCE(effective_to, 'infinity'::date)) WITH &&
    );

CREATE TABLE merchant.merchant_risk_profiles (
    id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id              BIGINT NOT NULL UNIQUE REFERENCES merchant.merchant_master(id),
    risk_score               NUMERIC(5,4) NOT NULL DEFAULT 0.10,
    risk_tier                ref.risk_tier NOT NULL DEFAULT 'low',
    chargeback_threshold_bps SMALLINT NOT NULL DEFAULT 100,
    velocity_limit_per_day   INTEGER NOT NULL DEFAULT 5000,
    max_ticket_amount        NUMERIC(18,2) NOT NULL DEFAULT 200000,
    last_reviewed_at         TIMESTAMPTZ,
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE merchant.merchant_settlement_configuration (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id       BIGINT NOT NULL UNIQUE REFERENCES merchant.merchant_master(id),
    settlement_cycle  TEXT NOT NULL DEFAULT 'T+1',
    settlement_window TIME NOT NULL DEFAULT '23:00',
    min_settlement_amount NUMERIC(18,2) NOT NULL DEFAULT 100,
    hold_payouts      BOOLEAN NOT NULL DEFAULT FALSE,
    rolling_reserve_pct NUMERIC(4,3) NOT NULL DEFAULT 0,
    bank_account_id   BIGINT REFERENCES merchant.merchant_bank_accounts(id),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE merchant.merchant_status_history (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id   BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    from_status   ref.lifecycle_status,
    to_status     ref.lifecycle_status NOT NULL,
    reason        TEXT,
    changed_by    TEXT,
    changed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE merchant.merchant_audit_log (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name    TEXT NOT NULL,
    row_pk        BIGINT NOT NULL,
    action        TEXT NOT NULL,                      -- INSERT / UPDATE / DELETE
    changed_by    TEXT NOT NULL DEFAULT current_user,
    diff          JSONB NOT NULL,
    changed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Secondary/performance indexes live in ../indexes/01_merchant_indexes.sql.
-- This file keeps only structure + correctness constraints (PK/FK/UNIQUE/
-- EXCLUDE/partial-unique that enforce business rules).
