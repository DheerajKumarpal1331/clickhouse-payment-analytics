FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /mlflow
COPY startup.sh /startup.sh
RUN chmod +x /startup.sh

EXPOSE 5000
HEALTHCHECK --interval=15s --timeout=5s --retries=10 \
    CMD curl -sf http://localhost:5000/health || exit 1

ENTRYPOINT ["/startup.sh"]
