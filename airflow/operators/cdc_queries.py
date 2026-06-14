"""Per-source CDC projections: normalized OLTP rows -> the flat ClickHouse
fact/dimension shape, keyed on the **external codes** (merchant_code, ...) the
warehouse uses as dimension keys — never the internal BIGINT FKs.

This mirrors the streaming path (kafka/producers/queries.py); Airflow's batch
ingestion is the scheduled, gap-filling complement to the Kafka producers and is
deliberately kept self-contained so the Airflow deployment carries no dependency
on the kafka package. Each projection selects the watermark column AS ``_wm`` and
the PK AS ``_id``; the PostgresToClickHouseOperator appends the incremental
``(wm, id)`` cursor predicate, ordering, and LIMIT.

``map`` turns one raw Postgres row (with ``_wm``/``_id`` already popped) into the
dict inserted into ClickHouse, so a source whose column names differ from the
fact's can be reconciled here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class CdcSource:
    ch_table: str                       # target ClickHouse table
    sql: str                            # SELECT ... (no WHERE/ORDER/LIMIT)
    wm: str                             # watermark column expression
    idc: str                           # primary-key expression (cursor tiebreaker)
    map: Callable[[dict], dict]         # raw PG row -> ClickHouse row


def _identity(row: dict) -> dict:
    return row


CDC_SOURCES: dict[str, CdcSource] = {
    # ---------------------------------------------------------------- merchant
    "merchant": CdcSource(
        ch_table="payments.dim_merchants",
        sql="""
        SELECT m.merchant_code                                  AS merchant_id,
               COALESCE(m.legal_name, '')                       AS legal_name,
               COALESCE(m.dba_name, '')                         AS dba_name,
               COALESCE(m.entity_type::text, '')                AS business_type,
               COALESCE(m.mcc, '')                              AS mcc,
               COALESCE(m.category, '')                         AS category,
               m.status::text                                   AS status,
               COALESCE(to_char(m.onboarded_date, 'YYYY-MM-DD'),
                        '1970-01-01')                           AS onboarded_date,
               to_char(m.updated_at, 'YYYY-MM-DD HH24:MI:SS')   AS event_time,
               m.id AS _id, m.updated_at AS _wm
        FROM merchant.merchant_master m
        """,
        wm="m.updated_at", idc="m.id", map=_identity),

    # ------------------------------------------------------------- transaction
    "transaction": CdcSource(
        ch_table="payments.fact_transactions",
        sql="""
        SELECT h.transaction_uid::text                          AS transaction_id,
               COALESCE(h.rrn, '')                              AS rrn,
               m.merchant_code                                  AS merchant_id,
               COALESCE(d.device_code, '')                      AS device_id,
               COALESCE(c.customer_code, '')                    AS customer_id,
               h.payment_method::text                           AS payment_method,
               COALESCE(h.channel, '')                          AS channel,
               COALESCE(h.mcc, '')                              AS mcc,
               h.amount::float8                                 AS amount,
               COALESCE(h.currency, 'INR')                      AS currency,
               h.is_success::int                                AS is_success,
               COALESCE(h.response_code, '')                    AS response_code,
               COALESCE(h.latitude, 0)::float8                  AS latitude,
               COALESCE(h.longitude, 0)::float8                 AS longitude,
               h.fraud_label::int                               AS fraud_label,
               to_char(h.created_at, 'YYYY-MM-DD HH24:MI:SS')   AS event_time,
               h.id AS _id, h.created_at AS _wm
        FROM txn.transaction_header h
        JOIN merchant.merchant_master m ON m.id = h.merchant_id
        LEFT JOIN device.device_master d ON d.id = h.device_id
        LEFT JOIN customer.customer_master c ON c.id = h.customer_id
        """,
        wm="h.created_at", idc="h.id", map=_identity),

    # ------------------------------------------------------------------ refund
    "refund": CdcSource(
        ch_table="payments.fact_refunds",
        sql="""
        SELECT r.refund_code                                    AS refund_id,
               r.transaction_id::text                           AS transaction_id,
               m.merchant_code                                  AS merchant_id,
               COALESCE(c.customer_code, '')                    AS customer_id,
               r.requested_amount::float8                       AS amount,
               COALESCE(r.original_amount, 0)::float8           AS original_amount,
               r.is_partial::int                                AS is_partial,
               COALESCE(r.reason::text, '')                     AS reason,
               COALESCE(r.initiated_by::text, '')               AS initiated_by,
               r.status::text                                   AS status,
               to_char(r.requested_at, 'YYYY-MM-DD HH24:MI:SS') AS event_time,
               r.id AS _id, r.requested_at AS _wm
        FROM refund.refund_requests r
        JOIN merchant.merchant_master m ON m.id = r.merchant_id
        LEFT JOIN customer.customer_master c ON c.id = r.customer_id
        """,
        wm="r.requested_at", idc="r.id", map=_identity),

    # -------------------------------------------------------------- settlement
    "settlement": CdcSource(
        ch_table="payments.fact_settlements",
        sql="""
        SELECT ms.batch_id::text                                AS settlement_batch_id,
               m.merchant_code                                  AS merchant_id,
               to_char(b.cycle_date, 'YYYY-MM-DD')             AS cycle_date,
               COALESCE(b.settlement_cycle, 'T+1')             AS settlement_cycle,
               ms.txn_count                                     AS txn_count,
               ms.gross_amount::float8                          AS gross_amount,
               COALESCE(ms.refund_amount, 0)::float8            AS refund_amount,
               COALESCE(ms.chargeback_amount, 0)::float8        AS chargeback_amount,
               COALESCE(ms.mdr_amount, 0)::float8               AS mdr_amount,
               COALESCE(ms.gst_amount, 0)::float8               AS gst_amount,
               ms.net_amount::float8                            AS net_amount,
               ms.status::text                                  AS status,
               ms.id AS _id, ms.created_at AS _wm
        FROM settlement.merchant_settlements ms
        JOIN merchant.merchant_master m ON m.id = ms.merchant_id
        JOIN settlement.settlement_batches b ON b.id = ms.batch_id
        """,
        wm="ms.created_at", idc="ms.id", map=_identity),
}
