-- ============================================================
-- 04: UPI + Card sub-domains
-- Method-specific detail tables that extend a transaction. Card
-- routing masters (issuer/acquirer/network/BIN) live in ref schema
-- (00_foundation); here we model the instrument-level records.
-- ============================================================

-- ---------- UPI ----------
CREATE TABLE txn.upi_vpa (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id   BIGINT REFERENCES customer.customer_master(id),
    vpa_masked    TEXT NOT NULL,
    psp_handle    TEXT NOT NULL,                  -- @okhdfcbank, @ybl, @paytm
    is_primary    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (vpa_masked)
);

CREATE TABLE txn.upi_transactions (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id  BIGINT NOT NULL,
    upi_txn_ref     TEXT NOT NULL,
    upi_flow        TEXT NOT NULL,                 -- intent / collect / qr / autopay
    payer_vpa       TEXT,
    payee_vpa       TEXT,
    psp_payer       TEXT,
    psp_payee       TEXT,
    npci_response   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE txn.upi_collect_requests (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    payer_vpa     TEXT NOT NULL,
    payee_vpa     TEXT NOT NULL,
    amount        NUMERIC(18,2) NOT NULL,
    expires_at    TIMESTAMPTZ NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending', -- pending / paid / expired / declined
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE txn.upi_mandates (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id   BIGINT REFERENCES customer.customer_master(id),
    merchant_id   BIGINT REFERENCES merchant.merchant_master(id),
    umn           TEXT NOT NULL UNIQUE,            -- unique mandate number
    max_amount    NUMERIC(18,2) NOT NULL,
    frequency     TEXT NOT NULL,                   -- monthly / weekly / as_presented
    valid_from    DATE NOT NULL,
    valid_to      DATE NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE txn.upi_autopay (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mandate_id    BIGINT NOT NULL REFERENCES txn.upi_mandates(id),
    transaction_id BIGINT,
    debit_amount  NUMERIC(18,2) NOT NULL,
    executed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    status        TEXT NOT NULL DEFAULT 'success'
);

-- ---------- Card ----------
CREATE TABLE txn.card_transactions (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id   BIGINT NOT NULL,
    card_bin         CHAR(6) REFERENCES ref.card_bin_master(bin),
    card_last4       CHAR(4),
    card_network     TEXT REFERENCES ref.card_network(network_code),
    issuer_bank      TEXT REFERENCES ref.bank(bank_code),
    acquirer_bank    TEXT REFERENCES ref.bank(bank_code),
    pos_entry_mode   TEXT,                          -- chip / contactless / swipe / manual / ecom
    emv_aid          TEXT,
    cvm_method       TEXT,
    is_emi           BOOLEAN NOT NULL DEFAULT FALSE,
    emi_tenure_months SMALLINT DEFAULT 0,
    network_txn_id   TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ref.terminal_capabilities (
    terminal_type   TEXT PRIMARY KEY,
    supports_chip   BOOLEAN NOT NULL DEFAULT TRUE,
    supports_nfc    BOOLEAN NOT NULL DEFAULT TRUE,
    supports_swipe  BOOLEAN NOT NULL DEFAULT TRUE,
    supports_pin    BOOLEAN NOT NULL DEFAULT TRUE,
    max_contactless_amount NUMERIC(18,2) DEFAULT 5000
);

-- Secondary indexes -> ../indexes/04_transaction_indexes.sql (UPI/card section)
