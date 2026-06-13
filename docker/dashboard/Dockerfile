# Plotly Dash analytics platform (Executive / Merchant / Fraud / Ops / Settlement / Support).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY docker/dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard/ /app/dashboard/
COPY docker/dashboard/startup.sh /startup.sh
RUN chmod +x /startup.sh

EXPOSE 8050
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -sf http://localhost:8050/ || exit 1

ENTRYPOINT ["/startup.sh"]
