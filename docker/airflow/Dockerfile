# Extends the official Airflow image with the platform's connector libs so
# DAGs can read ClickHouse / Postgres / Kafka. To use it, point the
# x-airflow-common `image:` at a build of this Dockerfile (or pre-build and
# push). Default compose uses the stock apache/airflow image + requirements
# baked here via _PIP_ADDITIONAL_REQUIREMENTS for dev convenience.
ARG AIRFLOW_VERSION=2.9.3
FROM apache/airflow:${AIRFLOW_VERSION}

COPY docker/airflow/requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
