# Kafka pipeline image — backs both kafka-producer (Postgres->Kafka) and
# kafka-consumer (Kafka->ClickHouse). The runner is chosen by the compose
# `command:`. Phase 4 delivers the ./kafka package.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY docker/kafka/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kafka/ /app/
COPY docker/kafka/startup.sh /startup.sh
RUN chmod +x /startup.sh

# Producers/consumers expose Prometheus metrics on :9000 (scraped by Prometheus).
EXPOSE 9000
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=5 \
    CMD curl -sf http://localhost:9000/metrics || exit 1

ENTRYPOINT ["/startup.sh"]
