"""Pydantic event contracts — the single source of truth for what flows over
the 8 Kafka topics.

Design: each model validates the **load-bearing core** strictly and sets
`extra='allow'`, so two producers can share one contract:
  - OLTP CDC (Postgres -> Kafka) emits the normalized operational columns;
  - the gateway/switch hot-path emits the full ~95-field enriched payload.
The ClickHouse consumer inserts JSONEachRow with skip-unknown + defaults, so
either width lands in the same fact table. Anything failing the core contract
is routed to the DLQ rather than crashing the consumer.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_METHODS = {"upi", "card", "debit_card", "credit_card", "wallet", "netbanking", "emi", "qr"}


class _Event(BaseModel):
    model_config = ConfigDict(extra="allow")  # tolerate the enriched superset

    @staticmethod
    def _check_ts(v: str) -> str:
        # accept 'YYYY-MM-DD HH:MM:SS[.fff]' or ISO 8601
        datetime.fromisoformat(v.replace(" ", "T")[:26])
        return v


class TransactionEvent(_Event):
    transaction_id: str = Field(min_length=6)
    merchant_id: str
    event_time: str
    amount: float = Field(gt=0, le=10_000_000)
    payment_method: str
    is_success: int = Field(ge=0, le=1)
    # common-but-optional core
    device_id: str = ""
    customer_id: str = ""
    rrn: str = ""
    currency: str = "INR"
    channel: str = ""
    mcc: str = ""
    response_code: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    fraud_label: int = Field(default=0, ge=0, le=1)

    @field_validator("payment_method")
    @classmethod
    def _method(cls, v: str) -> str:
        if v not in VALID_METHODS:
            raise ValueError(f"unknown payment_method: {v!r}")
        return v

    @field_validator("event_time")
    @classmethod
    def _ts(cls, v: str) -> str:
        return cls._check_ts(v)


class RefundEvent(_Event):
    refund_id: str
    transaction_id: str
    merchant_id: str
    event_time: str
    amount: float = Field(gt=0)
    reason: str = ""
    is_abusive: int = Field(default=0, ge=0, le=1)

    @field_validator("event_time")
    @classmethod
    def _ts(cls, v: str) -> str:
        return cls._check_ts(v)


class ChargebackEvent(_Event):
    chargeback_id: str
    transaction_id: str
    merchant_id: str
    event_time: str
    # amount lives in chargeback_financials and may be absent when a case opens.
    amount: float = Field(default=0.0, ge=0)
    reason_code: str = ""
    status: str = "open"


class SettlementEvent(_Event):
    settlement_batch_id: str
    merchant_id: str
    cycle_date: str
    net_amount: float
    txn_count: int = Field(ge=0)
    status: str = "pending"


class FraudEvent(_Event):
    event_id: str
    transaction_id: str
    merchant_id: str
    scored_at: str
    score: float = Field(ge=0, le=1)
    risk_level: str
    model_version: str = ""


class SupportEvent(_Event):
    ticket_id: str
    merchant_id: str = ""
    customer_id: str = ""
    category: str
    priority: str
    status: str
    event_time: str


class MerchantEvent(_Event):
    """Merchant onboarding / profile change (also seeds dim_merchants)."""
    merchant_id: str
    business_type: str = ""
    mcc: str = ""
    status: str = ""
    event_time: str = ""


class DeviceEvent(_Event):
    """Device lifecycle / health change."""
    device_id: str
    merchant_id: str = ""
    terminal_type: str = ""
    status: str = ""
    event_time: str = ""
