# Continuous OLTP generator — streams fresh transactions into Postgres, which
# the watermark-CDC producer then carries downstream. Tiny image: psycopg2 + the
# data_generator package (run as `python -m data_generator.live_postgres`).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
RUN pip install --no-cache-dir psycopg2-binary==2.9.9

COPY data_generator/ /app/data_generator/

ENTRYPOINT ["python", "-m", "data_generator.live_postgres"]
CMD ["--rate", "8", "--batch", "4"]
