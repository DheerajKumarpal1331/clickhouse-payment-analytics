"""Custom Airflow sensors for the payment-analytics platform.

- PostgresRowSensor        : poke until the OLTP source has rows past the CDC
                             cursor (there is fresh data to ingest)
- ClickHousePartitionSensor : poke until a ClickHouse table has at least N rows
                             (optionally for a given date) — a freshness gate for
                             downstream feature/mart/training tasks
"""
from .postgres_sensor import PostgresRowSensor
from .clickhouse_sensor import ClickHousePartitionSensor

__all__ = ["PostgresRowSensor", "ClickHousePartitionSensor"]
