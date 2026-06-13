"""Topic registry — the wiring table that binds each Kafka topic to its
validation schema, partition key, and ClickHouse sink table. Producers,
consumers, the DLQ handler and the topic creator all read from here, so the
8-topic contract is defined in exactly one place.
"""
from __future__ import annotations

from dataclasses import dataclass

from .events import (TransactionEvent, RefundEvent, ChargebackEvent, SettlementEvent,
                     FraudEvent, SupportEvent, MerchantEvent, DeviceEvent)


@dataclass(frozen=True)
class TopicSpec:
    name: str
    schema: type            # Pydantic event model
    key_field: str          # message key (co-partitions a merchant's events)
    ch_table: str           # ClickHouse sink (db-qualified at runtime)
    # Postgres source for the CDC producer (schema-qualified table + watermark col).
    pg_source: str
    pg_watermark: str = "updated_at"

    @property
    def dlq(self) -> str:
        return f"{self.name}.dlq"


TOPICS: dict[str, TopicSpec] = {
    "transaction_events": TopicSpec(
        "transaction_events", TransactionEvent, "merchant_id",
        ch_table="fact_transactions", pg_source="txn.transaction_header", pg_watermark="created_at"),
    "refund_events": TopicSpec(
        "refund_events", RefundEvent, "merchant_id",
        ch_table="fact_refunds", pg_source="refund.refund_requests", pg_watermark="requested_at"),
    "chargeback_events": TopicSpec(
        "chargeback_events", ChargebackEvent, "merchant_id",
        ch_table="fact_chargebacks", pg_source="chargeback.chargeback_cases", pg_watermark="opened_at"),
    "settlement_events": TopicSpec(
        "settlement_events", SettlementEvent, "merchant_id",
        ch_table="fact_settlements", pg_source="settlement.merchant_settlements", pg_watermark="created_at"),
    "fraud_events": TopicSpec(
        "fraud_events", FraudEvent, "merchant_id",
        ch_table="fact_fraud_events", pg_source="fraud.fraud_scores", pg_watermark="scored_at"),
    "support_events": TopicSpec(
        "support_events", SupportEvent, "merchant_id",
        ch_table="fact_support_events", pg_source="support.support_tickets", pg_watermark="created_at"),
    "merchant_events": TopicSpec(
        "merchant_events", MerchantEvent, "merchant_id",
        ch_table="dim_merchants", pg_source="merchant.merchant_master", pg_watermark="updated_at"),
    "device_events": TopicSpec(
        "device_events", DeviceEvent, "device_id",
        ch_table="fact_device_events", pg_source="device.device_master", pg_watermark="updated_at"),
}

ALL_TOPICS = list(TOPICS)
