-- ============================================================
-- Trigger functions (PL/pgSQL)
-- Apply order: ddl/ -> indexes/ -> procedures/01 -> 02 -> 03.
-- Functions are CREATE OR REPLACE so re-runs are idempotent.
-- ============================================================

-- ---------- updated_at touch ----------
CREATE OR REPLACE FUNCTION ref.touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$ LANGUAGE plpgsql;

-- ---------- generic row audit into <schema>.<x>_audit_log ----------
-- Writes a JSONB diff; target log table passed via the trigger arg.
CREATE OR REPLACE FUNCTION ref.audit_row() RETURNS trigger AS $$
DECLARE
    log_table TEXT := TG_ARGV[0];
    pk        BIGINT;
    diff      JSONB;
BEGIN
    IF TG_OP = 'DELETE' THEN
        pk := OLD.id; diff := to_jsonb(OLD);
    ELSIF TG_OP = 'UPDATE' THEN
        pk := NEW.id;
        diff := jsonb_build_object(
            'old', to_jsonb(OLD) - 'updated_at',
            'new', to_jsonb(NEW) - 'updated_at');
    ELSE
        pk := NEW.id; diff := to_jsonb(NEW);
    END IF;

    EXECUTE format(
        'INSERT INTO %s (table_name, row_pk, action, diff) VALUES ($1,$2,$3,$4)',
        log_table)
    USING TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME, pk, TG_OP, diff;

    RETURN COALESCE(NEW, OLD);
END $$ LANGUAGE plpgsql;

-- ---------- merchant status-history capture ----------
CREATE OR REPLACE FUNCTION merchant.log_status_change() RETURNS trigger AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO merchant.merchant_status_history
            (merchant_id, from_status, to_status, changed_by)
        VALUES (NEW.id, OLD.status, NEW.status, current_user);
    END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;

-- ---------- transaction state-history capture ----------
CREATE OR REPLACE FUNCTION txn.log_state_change() RETURNS trigger AS $$
BEGIN
    IF NEW.state IS DISTINCT FROM OLD.state THEN
        INSERT INTO txn.transaction_status_history
            (transaction_id, from_state, to_state)
        VALUES (NEW.id, OLD.state, NEW.state);
    END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;
