#!/usr/bin/env bash
# ============================================================
# Kafka IaC — create the 8 domain topics + their DLQ siblings with
# partitions / replication / retention from the environment. Idempotent
# (--if-not-exists), so re-running on restart is safe.
# ============================================================
set -euo pipefail

BS="${KAFKA_BOOTSTRAP:-kafka:29092}"
P="${KAFKA_TOPIC_PARTITIONS:-6}"
R="${KAFKA_TOPIC_REPLICATION:-1}"
RET="${KAFKA_RETENTION_MS:-604800000}"

TOPICS=(
  merchant_events device_events transaction_events refund_events
  settlement_events chargeback_events support_events fraud_events
)

echo "==> waiting for broker at $BS"
for _ in $(seq 1 30); do
  kafka-broker-api-versions --bootstrap-server "$BS" >/dev/null 2>&1 && break
  sleep 2
done

create() {  # name partitions retention
  kafka-topics --create --if-not-exists --bootstrap-server "$BS" \
    --topic "$1" --partitions "$2" --replication-factor "$R" \
    --config retention.ms="$3" --config compression.type=producer
}

for t in "${TOPICS[@]}"; do
  echo "==> $t (p=$P r=$R)"
  create "$t" "$P" "$RET"
  # DLQ: single partition, 4x retention so failures aren't lost before replay
  create "$t.dlq" 1 "$((RET * 4))"
done

echo "==> topics now present:"
kafka-topics --bootstrap-server "$BS" --list | sort
