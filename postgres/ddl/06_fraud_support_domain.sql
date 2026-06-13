-- ============================================================
-- 06: Fraud + Support domains
-- ============================================================

-- ---------- Fraud ----------
CREATE TABLE fraud.fraud_rules (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_code     TEXT NOT NULL UNIQUE,
    description   TEXT NOT NULL,
    rule_type     TEXT NOT NULL,                    -- velocity / amount / geo / device / mcc
    expression    TEXT NOT NULL,                    -- DSL / SQL predicate
    severity      ref.risk_tier NOT NULL DEFAULT 'medium',
    action        TEXT NOT NULL DEFAULT 'flag',     -- flag / hold / block / step_up
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fraud.fraud_scores (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id  BIGINT NOT NULL,
    merchant_id     BIGINT REFERENCES merchant.merchant_master(id),
    model_version   TEXT NOT NULL,
    score           NUMERIC(6,5) NOT NULL,
    risk_level      ref.risk_tier NOT NULL,
    reason_codes    TEXT[] NOT NULL DEFAULT '{}',
    latency_ms      NUMERIC(8,2),
    scored_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fraud.fraud_alerts (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transaction_id  BIGINT,
    merchant_id     BIGINT REFERENCES merchant.merchant_master(id),
    rule_id         BIGINT REFERENCES fraud.fraud_rules(id),
    score_id        BIGINT REFERENCES fraud.fraud_scores(id),
    severity        ref.risk_tier NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open',   -- open / triaged / dismissed / confirmed
    raised_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fraud.fraud_cases (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_code       TEXT NOT NULL UNIQUE,
    merchant_id     BIGINT REFERENCES merchant.merchant_master(id),
    customer_id     BIGINT REFERENCES customer.customer_master(id),
    fraud_type      TEXT NOT NULL,                  -- card_testing / device_takeover / ...
    estimated_loss  NUMERIC(18,2) NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'investigating',
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at       TIMESTAMPTZ
);

CREATE TABLE fraud.fraud_investigations (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_id     BIGINT NOT NULL REFERENCES fraud.fraud_cases(id),
    investigator TEXT NOT NULL,
    notes       TEXT,
    finding     TEXT,                               -- confirmed_fraud / false_positive / inconclusive
    logged_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fraud.merchant_blacklists (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    reason      TEXT NOT NULL,
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (merchant_id)
);

CREATE TABLE fraud.device_blacklists (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    device_fingerprint TEXT NOT NULL UNIQUE,
    reason      TEXT NOT NULL,
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    active      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE fraud.customer_blacklists (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customer.customer_master(id),
    reason      TEXT NOT NULL,
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (customer_id)
);

-- ---------- Support ----------
CREATE TABLE support.support_tickets (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_code   TEXT NOT NULL UNIQUE,
    merchant_id   BIGINT REFERENCES merchant.merchant_master(id),
    customer_id   BIGINT REFERENCES customer.customer_master(id),
    category      TEXT NOT NULL,                    -- settlement / device / txn_dispute / kyc
    priority      TEXT NOT NULL DEFAULT 'medium',
    subject       TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'open',
    assigned_to   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at   TIMESTAMPTZ
);

CREATE TABLE support.ticket_comments (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id   BIGINT NOT NULL REFERENCES support.support_tickets(id),
    author      TEXT NOT NULL,
    body        TEXT NOT NULL,
    is_internal BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE support.ticket_status_history (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id   BIGINT NOT NULL REFERENCES support.support_tickets(id),
    from_status TEXT, to_status TEXT NOT NULL,
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE support.ticket_escalations (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id   BIGINT NOT NULL REFERENCES support.support_tickets(id),
    escalated_to TEXT NOT NULL,
    level       SMALLINT NOT NULL DEFAULT 1,
    escalated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE support.sla_tracking (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id     BIGINT NOT NULL UNIQUE REFERENCES support.support_tickets(id),
    sla_target_mins INTEGER NOT NULL,
    first_response_at TIMESTAMPTZ,
    resolution_due_at TIMESTAMPTZ NOT NULL,
    breached      BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE support.merchant_complaints (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    merchant_id BIGINT NOT NULL REFERENCES merchant.merchant_master(id),
    ticket_id   BIGINT REFERENCES support.support_tickets(id),
    complaint   TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE support.customer_complaints (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES customer.customer_master(id),
    ticket_id   BIGINT REFERENCES support.support_tickets(id),
    complaint   TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Secondary indexes -> ../indexes/06_fraud_support_indexes.sql
