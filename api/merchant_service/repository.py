"""Merchant-domain reads against the Postgres OLTP (Phase 2 schema).
Parameterized SQL; joins masters to their risk/pricing/assignment satellites.
"""
from __future__ import annotations

from api.common import postgres as pg


def get_merchant(code: str) -> dict:
    return pg.query_one(
        """
        SELECT m.merchant_code, m.legal_name, m.dba_name, m.mcc, m.category,
               m.entity_type, m.status, m.onboarded_date, m.activation_date,
               r.risk_tier, r.risk_score, r.velocity_limit_per_day, r.max_ticket_amount,
               p.pricing_plan, p.mdr_card_credit_bps, p.mdr_upi_bps
        FROM merchant.merchant_master m
        LEFT JOIN merchant.merchant_risk_profiles r ON r.merchant_id = m.id
        LEFT JOIN merchant.merchant_pricing p
               ON p.merchant_id = m.id AND p.effective_to IS NULL
        WHERE m.merchant_code = %s
        """, (code,))


def list_merchants(status: str | None, mcc: str | None, limit: int) -> list[dict]:
    where, params = [], []
    if status:
        where.append("m.status = %s"); params.append(status)
    if mcc:
        where.append("m.mcc = %s"); params.append(mcc)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    params.append(limit)
    return pg.query(
        f"""
        SELECT m.merchant_code, m.dba_name, m.mcc, m.category, m.status,
               m.onboarded_date, r.risk_tier
        FROM merchant.merchant_master m
        LEFT JOIN merchant.merchant_risk_profiles r ON r.merchant_id = m.id
        {clause}
        ORDER BY m.onboarded_date DESC
        LIMIT %s
        """, tuple(params))


def get_device(code: str) -> dict:
    return pg.query_one(
        """
        SELECT d.device_code, d.serial_number, d.terminal_id, d.terminal_type,
               d.manufacturer, d.model, a.store_id, a.assigned_at,
               mm.merchant_code AS assigned_merchant
        FROM device.device_master d
        LEFT JOIN device.device_assignment a ON a.device_id = d.id AND a.released_at IS NULL
        LEFT JOIN merchant.merchant_master mm ON mm.id = a.merchant_id
        WHERE d.device_code = %s
        """, (code,))


def list_devices(merchant_code: str | None, limit: int) -> list[dict]:
    if merchant_code:
        return pg.query(
            """
            SELECT d.device_code, d.terminal_type, d.manufacturer, a.store_id, a.assigned_at
            FROM device.device_assignment a
            JOIN device.device_master d ON d.id = a.device_id
            JOIN merchant.merchant_master m ON m.id = a.merchant_id
            WHERE m.merchant_code = %s AND a.released_at IS NULL
            ORDER BY a.assigned_at DESC LIMIT %s
            """, (merchant_code, limit))
    return pg.query(
        "SELECT device_code, terminal_type, manufacturer, model FROM device.device_master "
        "ORDER BY created_at DESC LIMIT %s", (limit,))


def get_customer(code: str) -> dict:
    return pg.query_one(
        """
        SELECT c.customer_code, c.age_band, c.gender, c.kyc_level, c.status,
               c.first_seen_date, r.risk_profile, r.risk_score, r.is_blacklisted,
               r.lifetime_txn_count, r.lifetime_spend
        FROM customer.customer_master c
        LEFT JOIN customer.customer_risk_profiles r ON r.customer_id = c.id
        WHERE c.customer_code = %s
        """, (code,))
