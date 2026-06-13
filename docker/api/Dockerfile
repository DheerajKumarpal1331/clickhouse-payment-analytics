# Shared image for the three FastAPI services (merchant / analytics / fraud).
# The SERVICE env var selects which app module uvicorn serves at runtime,
# so one image backs merchant-api, analytics-api and fraud-api.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY docker/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code lands in ./api (delivered in the API phase).
COPY api/ /app/api/
COPY docker/api/startup.sh /startup.sh
RUN chmod +x /startup.sh

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -sf http://localhost:8000/health || exit 1

ENTRYPOINT ["/startup.sh"]
