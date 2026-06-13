# Feature store materializer — computes offline (point-in-time) and online
# (latest) features in ClickHouse. Run as a long-running refresher (compose
# `ml` profile) or scheduled by Airflow. Code is the ./feature_store package
# (Phase 6); its modules use flat imports, so contents land directly on /app.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY docker/feature-store/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY feature_store/ /app/
COPY docker/feature-store/startup.sh /startup.sh
RUN chmod +x /startup.sh

EXPOSE 9000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -sf http://localhost:9000/metrics || exit 1

ENTRYPOINT ["/startup.sh"]
CMD ["python", "-m", "refresh", "--loop"]
