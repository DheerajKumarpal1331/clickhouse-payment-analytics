-- ============================================================
-- 02: Device + Customer domains (3NF)
-- ============================================================

-- ---------- Device domain ----------
CREATE TABLE device.device_master (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_code     TEXT NOT NULL UNIQUE,
    serial_number   TEXT NOT NULL UNIQUE,
    terminal_id     CHAR(8) NOT NULL,
    terminal_type   TEXT NOT NULL,                    -- android_smartpos / linux_pos / mpos / soundbox / ecom
    manufacturer    TEXT,
    model           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE device.device_inventory (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id     BIGINT NOT NULL UNIQUE REFERENCES device.device_master(id),
    warehouse     TEXT NOT NULL,
    stock_status  TEXT NOT NULL DEFAULT 'in_stock',  -- in_stock / dispatched / deployed / returned / scrapped
    received_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE device.device_assignment (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id     BIGINT NOT NULL REFERENCES device.device_master(id),
    merchant_id   BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    store_id      TEXT,
    assigned_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    released_at   TIMESTAMPTZ,
    CHECK (released_at IS NULL OR released_at > assigned_at)
);
-- a device can be live at only one merchant at a time
CREATE UNIQUE INDEX uq_device_active_assignment
    ON device.device_assignment (device_id) WHERE released_at IS NULL;

CREATE TABLE device.device_activation (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id     BIGINT NOT NULL UNIQUE REFERENCES device.device_master(id),
    activated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    activated_by  TEXT,
    tms_profile   TEXT                                -- terminal mgmt system profile
);

CREATE TABLE device.device_firmware (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id        BIGINT NOT NULL REFERENCES device.device_master(id),
    firmware_version TEXT NOT NULL,
    app_version      TEXT,
    os_version       TEXT,
    pushed_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_current       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE device.device_network_status (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id     BIGINT NOT NULL REFERENCES device.device_master(id),
    network_type  TEXT NOT NULL,                       -- 4g / wifi / ethernet / 2g
    sim_operator  TEXT,
    signal_dbm    SMALLINT,
    observed_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE device.device_health (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id        BIGINT NOT NULL REFERENCES device.device_master(id),
    battery_level    SMALLINT,
    battery_health   TEXT DEFAULT 'good',
    last_heartbeat   TIMESTAMPTZ,
    txn_success_24h  INTEGER DEFAULT 0,
    txn_failure_24h  INTEGER DEFAULT 0,
    health_score     NUMERIC(4,3) DEFAULT 1.0,
    observed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE device.device_location (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id    BIGINT NOT NULL REFERENCES device.device_master(id),
    latitude     DOUBLE PRECISION,
    longitude    DOUBLE PRECISION,
    accuracy_m   SMALLINT,
    observed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE device.device_repair_history (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_id     BIGINT NOT NULL REFERENCES device.device_master(id),
    issue         TEXT NOT NULL,
    action_taken  TEXT,
    cost_paise    INTEGER DEFAULT 0,
    repaired_at   TIMESTAMPTZ,
    reported_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE device.device_audit_log (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    table_name  TEXT NOT NULL, row_pk BIGINT NOT NULL, action TEXT NOT NULL,
    changed_by  TEXT NOT NULL DEFAULT current_user, diff JSONB NOT NULL,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Secondary indexes -> ../indexes/02_device_indexes.sql

-- ---------- Customer domain ----------
CREATE TABLE customer.customer_master (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_code    TEXT NOT NULL UNIQUE,
    age_band         TEXT,
    gender           CHAR(1),
    phone_hash       TEXT NOT NULL,
    email_hash       TEXT,
    home_location_id BIGINT REFERENCES ref.location(location_id),
    kyc_level        TEXT NOT NULL DEFAULT 'min',     -- min / full
    first_seen_date  DATE NOT NULL DEFAULT CURRENT_DATE,
    status           ref.lifecycle_status NOT NULL DEFAULT 'active',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE customer.customer_devices (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id        BIGINT NOT NULL REFERENCES customer.customer_master(id),
    device_fingerprint TEXT NOT NULL,
    os                 TEXT,
    app_version        TEXT,
    first_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (customer_id, device_fingerprint)
);

CREATE TABLE customer.customer_addresses (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id  BIGINT NOT NULL REFERENCES customer.customer_master(id),
    location_id  BIGINT REFERENCES ref.location(location_id),
    address_type TEXT NOT NULL DEFAULT 'home',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE customer.customer_risk_profiles (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id   BIGINT NOT NULL UNIQUE REFERENCES customer.customer_master(id),
    risk_profile  ref.risk_tier NOT NULL DEFAULT 'low',
    risk_score    NUMERIC(5,4) NOT NULL DEFAULT 0.05,
    is_blacklisted BOOLEAN NOT NULL DEFAULT FALSE,
    lifetime_txn_count INTEGER NOT NULL DEFAULT 0,
    lifetime_spend NUMERIC(18,2) NOT NULL DEFAULT 0,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE customer.customer_payment_preferences (
    id               BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id      BIGINT NOT NULL UNIQUE REFERENCES customer.customer_master(id),
    preferred_method ref.payment_method NOT NULL DEFAULT 'upi',
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE customer.customer_consent (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id   BIGINT NOT NULL REFERENCES customer.customer_master(id),
    consent_type  TEXT NOT NULL,                       -- marketing / data_share / autopay
    granted       BOOLEAN NOT NULL,
    granted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (customer_id, consent_type)
);

-- Secondary indexes -> ../indexes/03_customer_indexes.sql
