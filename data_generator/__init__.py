"""Synthetic payment ecosystem generator.

Modules
-------
reference            shared constants + temporal/holiday/salary-day curves
merchant_generator   merchant master (KYC, pricing, risk, lifecycle)
customer_generator   customers (demographics, hashed PII, risk)
device_generator     POS terminals bound to merchants
transaction_generator core stream with realistic day/hour shaping + fraud
fraud_generator      fraud-burst scenarios (velocity, card-testing, takeover, ...)
refund_generator     refunds + chargebacks (incl. refund-abuse)
enrichment           ISO 8583 / EMV / 3DS / fee enrichment per transaction
generate             CLI: historical (Parquet) | stream (Kafka)
"""
