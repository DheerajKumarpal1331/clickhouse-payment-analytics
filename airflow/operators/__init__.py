"""Custom Airflow operators for the payment-analytics platform.

These wrap the platform's two stores with dependency-light clients (stdlib
`urllib` for ClickHouse, `psycopg2` — already in the Airflow image — for
Postgres) so the Airflow deployment needs no extra drivers.

- PostgresToClickHouseOperator : watermark CDC, Postgres OLTP -> ClickHouse facts
- ClickHouseOperator           : run one or more SQL statements on ClickHouse
- DataQualityOperator          : assert SQL-metric expectations, fail on breach
"""
from .pg_to_clickhouse import PostgresToClickHouseOperator
from .clickhouse_operator import ClickHouseOperator
from .data_quality_operator import DataQualityOperator

__all__ = [
    "PostgresToClickHouseOperator",
    "ClickHouseOperator",
    "DataQualityOperator",
]
