-- ============================================================
-- 00: Foundation — extensions, schemas, shared enums & helpers
--
-- OLTP design notes
-- -----------------
-- * One Postgres schema per business domain (merchant, device, ...)
--   keeps grants and search_path tidy and mirrors team ownership.
-- * Money is NUMERIC(18,2/4) — never float — paise-accurate.
-- * Every mutable table carries created_at / updated_at; a shared
--   trigger (10_triggers_functions.sql) maintains updated_at and
--   writes row-level audit JSON to <domain>.*_audit_log tables.
-- * Natural keys (merchant_code, RRN, ...) are UNIQUE; surrogate
--   BIGINT identity PKs drive FKs for narrow, stable joins.
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- gen_random_uuid, digest()
CREATE EXTENSION IF NOT EXISTS btree_gist;   -- exclusion constraints
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- fuzzy merchant search

CREATE SCHEMA IF NOT EXISTS merchant;
CREATE SCHEMA IF NOT EXISTS device;
CREATE SCHEMA IF NOT EXISTS customer;
CREATE SCHEMA IF NOT EXISTS txn;
CREATE SCHEMA IF NOT EXISTS settlement;
CREATE SCHEMA IF NOT EXISTS refund;
CREATE SCHEMA IF NOT EXISTS chargeback;
CREATE SCHEMA IF NOT EXISTS fraud;
CREATE SCHEMA IF NOT EXISTS support;
CREATE SCHEMA IF NOT EXISTS ref;             -- reference / lookup master data

-- ---------- Shared enums ----------
CREATE TYPE ref.lifecycle_status AS ENUM
    ('draft','pending','active','suspended','dormant','churned','closed');
CREATE TYPE ref.risk_tier AS ENUM ('low','medium','high','critical');
CREATE TYPE ref.kyc_status AS ENUM ('not_started','pending','verified','rejected','expired');
CREATE TYPE ref.payment_method AS ENUM ('upi','debit_card','credit_card','wallet','emi','qr','netbanking');
CREATE TYPE ref.txn_state AS ENUM
    ('initiated','authorized','captured','failed','reversed','refunded','partially_refunded');
CREATE TYPE ref.settlement_state AS ENUM ('pending','batched','initiated','paid','failed','on_hold');

-- ---------- Reference master data ----------
CREATE TABLE ref.merchant_category (
    mcc            CHAR(4) PRIMARY KEY,
    category_name  TEXT NOT NULL,
    segment        TEXT NOT NULL,            -- grocery, retail, pharmacy, ...
    risk_weight    NUMERIC(4,3) NOT NULL DEFAULT 0.100
);

CREATE TABLE ref.payment_method_dim (
    method_code    ref.payment_method PRIMARY KEY,
    display_name   TEXT NOT NULL,
    is_card        BOOLEAN NOT NULL,
    settles_t_plus SMALLINT NOT NULL DEFAULT 1
);

CREATE TABLE ref.location (
    location_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    city           TEXT NOT NULL,
    state          TEXT NOT NULL,
    pincode        CHAR(6),
    latitude       DOUBLE PRECISION,
    longitude      DOUBLE PRECISION,
    tier           SMALLINT,                 -- metro tiering 1/2/3
    UNIQUE (city, state, pincode)
);

CREATE TABLE ref.bank (
    bank_code      TEXT PRIMARY KEY,         -- HDFC, ICICI, ...
    bank_name      TEXT NOT NULL,
    is_issuer      BOOLEAN NOT NULL DEFAULT TRUE,
    is_acquirer    BOOLEAN NOT NULL DEFAULT FALSE,
    ifsc_prefix    CHAR(4)
);

CREATE TABLE ref.card_network (
    network_code   TEXT PRIMARY KEY,         -- visa, mastercard, rupay, amex
    network_name   TEXT NOT NULL,
    interchange_share NUMERIC(4,3) NOT NULL DEFAULT 0.700
);

CREATE TABLE ref.card_bin_master (
    bin            CHAR(6) PRIMARY KEY,
    network_code   TEXT REFERENCES ref.card_network(network_code),
    issuer_bank    TEXT REFERENCES ref.bank(bank_code),
    card_type      TEXT NOT NULL,            -- credit / debit / prepaid
    card_tier      TEXT,                     -- classic / gold / platinum / corporate
    country        CHAR(2) NOT NULL DEFAULT 'IN'
);

COMMENT ON SCHEMA merchant   IS 'Merchant onboarding, KYC, pricing, risk, audit';
COMMENT ON SCHEMA txn        IS 'Transaction lifecycle: header/details/attempts/auth/capture/fees';
COMMENT ON TABLE ref.card_bin_master IS 'BIN→network/issuer routing master used by the switch';
