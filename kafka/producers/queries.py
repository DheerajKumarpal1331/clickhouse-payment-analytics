"""Per-topic projection SQL: turn the normalized OLTP rows into the flat event
shape the topic's schema expects.

Each query joins `merchant_master` (and customer/device masters for transactions)
so the event carries the **external codes** (merchant_code, ...) used as the
Kafka key and ClickHouse dimension key — never the internal BIGINT FKs. Every
query selects the watermark column AS `_wm` and the PK AS `_id`; the incremental
reader (db_source) appends the cursor predicate, ordering and LIMIT.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Query:
    sql: str       # SELECT ... FROM ... JOIN ...  (no WHERE/ORDER/LIMIT)
    wm: str        # watermark column expression (for the cursor predicate)
    idc: str       # primary-key column expression (cursor tiebreaker)


QUERIES: dict[str, Query] = {
    "transaction_events": Query(
        sql="""
        SELECT h.transaction_uid::text                         AS transaction_id,
               m.merchant_code                                 AS merchant_id,
               COALESCE(d.device_code, '')                     AS device_id,
               COALESCE(c.customer_code, '')                   AS customer_id,
               h.rrn, h.payment_method::text                   AS payment_method,
               h.channel, h.mcc, h.amount::float8              AS amount, h.currency,
               h.is_success::int                               AS is_success,
               COALESCE(h.response_code, '')                   AS response_code,
               COALESCE(h.latitude, 0)                         AS latitude,
               COALESCE(h.longitude, 0)                        AS longitude,
               h.fraud_label::int                              AS fraud_label,
               to_char(h.created_at, 'YYYY-MM-DD HH24:MI:SS')  AS event_time,
               h.id AS _id, h.created_at AS _wm
        FROM txn.transaction_header h
        JOIN merchant.merchant_master m ON m.id = h.merchant_id
        LEFT JOIN device.device_master d ON d.id = h.device_id
        LEFT JOIN customer.customer_master c ON c.id = h.customer_id
        """, wm="h.created_at", idc="h.id"),

    "refund_events": Query(
        sql="""
        SELECT r.refund_code                                   AS refund_id,
               r.transaction_id::text                          AS transaction_id,
               m.merchant_code                                 AS merchant_id,
               r.requested_amount::float8                      AS amount,
               COALESCE(r.reason::text, '')                    AS reason,
               to_char(r.requested_at, 'YYYY-MM-DD HH24:MI:SS') AS event_time,
               r.id AS _id, r.requested_at AS _wm
        FROM refund.refund_requests r
        JOIN merchant.merchant_master m ON m.id = r.merchant_id
        """, wm="r.requested_at", idc="r.id"),

    "chargeback_events": Query(
        sql="""
        SELECT cc.case_code                                    AS chargeback_id,
               cc.transaction_id::text                         AS transaction_id,
               m.merchant_code                                 AS merchant_id,
               COALESCE(cf.dispute_amount, 0)::float8          AS amount,
               cc.reason_code::text                            AS reason_code,
               cc.status::text                                 AS status,
               to_char(cc.opened_at, 'YYYY-MM-DD HH24:MI:SS')  AS event_time,
               cc.id AS _id, cc.opened_at AS _wm
        FROM chargeback.chargeback_cases cc
        JOIN merchant.merchant_master m ON m.id = cc.merchant_id
        LEFT JOIN chargeback.chargeback_financials cf ON cf.case_id = cc.id
        """, wm="cc.opened_at", idc="cc.id"),

    "settlement_events": Query(
        sql="""
        SELECT ms.batch_id::text                               AS settlement_batch_id,
               m.merchant_code                                 AS merchant_id,
               to_char(b.cycle_date, 'YYYY-MM-DD')             AS cycle_date,
               ms.net_amount::float8                           AS net_amount,
               ms.txn_count, ms.status::text                   AS status,
               ms.id AS _id, ms.created_at AS _wm
        FROM settlement.merchant_settlements ms
        JOIN merchant.merchant_master m ON m.id = ms.merchant_id
        JOIN settlement.settlement_batches b ON b.id = ms.batch_id
        """, wm="ms.created_at", idc="ms.id"),

    "fraud_events": Query(
        sql="""
        SELECT fs.id::text                                     AS event_id,
               fs.transaction_id::text                         AS transaction_id,
               m.merchant_code                                 AS merchant_id,
               fs.score::float8                                AS score,
               fs.risk_level::text                             AS risk_level,
               COALESCE(fs.model_version, '')                  AS model_version,
               to_char(fs.scored_at, 'YYYY-MM-DD HH24:MI:SS')  AS scored_at,
               fs.id AS _id, fs.scored_at AS _wm
        FROM fraud.fraud_scores fs
        JOIN merchant.merchant_master m ON m.id = fs.merchant_id
        """, wm="fs.scored_at", idc="fs.id"),

    "support_events": Query(
        sql="""
        SELECT st.ticket_code                                  AS ticket_id,
               COALESCE(m.merchant_code, '')                   AS merchant_id,
               COALESCE(c.customer_code, '')                   AS customer_id,
               st.category::text                               AS category,
               st.priority::text                               AS priority,
               st.status::text                                 AS status,
               to_char(st.created_at, 'YYYY-MM-DD HH24:MI:SS') AS event_time,
               st.id AS _id, st.created_at AS _wm
        FROM support.support_tickets st
        LEFT JOIN merchant.merchant_master m ON m.id = st.merchant_id
        LEFT JOIN customer.customer_master c ON c.id = st.customer_id
        """, wm="st.created_at", idc="st.id"),

    "merchant_events": Query(
        sql="""
        SELECT m.merchant_code                                 AS merchant_id,
               COALESCE(m.category, '')                        AS business_type,
               m.mcc, m.status::text                           AS status,
               to_char(m.updated_at, 'YYYY-MM-DD HH24:MI:SS')  AS event_time,
               m.id AS _id, m.updated_at AS _wm
        FROM merchant.merchant_master m
        """, wm="m.updated_at", idc="m.id"),

    "device_events": Query(
        sql="""
        SELECT dm.device_code                                  AS device_id,
               COALESCE(m.merchant_code, '')                   AS merchant_id,
               dm.terminal_type::text                          AS terminal_type,
               CASE WHEN dact.device_id IS NOT NULL
                    THEN 'ACTIVE' ELSE 'INACTIVE' END          AS status,
               to_char(dm.updated_at, 'YYYY-MM-DD HH24:MI:SS') AS event_time,
               dm.id AS _id, dm.updated_at AS _wm
        FROM device.device_master dm
        LEFT JOIN device.device_assignment da ON da.device_id = dm.id AND da.released_at IS NULL
        LEFT JOIN merchant.merchant_master m ON m.id = da.merchant_id
        LEFT JOIN device.device_activation dact ON dact.device_id = dm.id
        """, wm="dm.updated_at", idc="dm.id"),
}
