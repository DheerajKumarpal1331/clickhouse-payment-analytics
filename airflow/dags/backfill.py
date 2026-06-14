"""backfill — manual, parameterised re-load of one CDC source over a window.

Rewinds the source's persisted ``(wm, id)`` cursor to ``from_ts`` and re-runs the
ingestion, so a fixed upstream bug, a schema change, or a cold start can be
replayed without touching the streaming path. Re-loads are idempotent: dimension
targets are ReplacingMergeTree and the facts are keyed, so a replayed window
dedupes/supersedes on merge rather than duplicating.

Trigger from the UI / CLI with conf, e.g.::

    airflow dags trigger backfill --conf '{"source":"transaction","from_ts":"2024-01-01 00:00:00"}'

schedule=None — this DAG only ever runs on demand.
"""
from __future__ import annotations

from airflow import DAG
from airflow.models.param import Param
from airflow.operators.python import PythonOperator

from common import DEFAULT_ARGS, START, TAGS
from operators import PostgresToClickHouseOperator
from operators import clients
from operators.cdc_queries import CDC_SOURCES


def rewind_cursor(**context):
    """Rewind the chosen source's watermark to from_ts (id reset to 0)."""
    params = context["params"]
    source = params["source"]
    from_ts = params["from_ts"]
    if source not in CDC_SOURCES:
        raise ValueError(f"unknown CDC source '{source}'; known: {sorted(CDC_SOURCES)}")
    prev = clients.get_watermark(source)
    clients.reset_watermark(source, wm=from_ts, last_id=0)
    print(f"backfill: rewound '{source}' cursor {prev} -> ({from_ts!r}, 0)")
    return source


with DAG(
    dag_id="backfill",
    description="Manual parameterised re-load of one CDC source from a chosen timestamp",
    default_args={**DEFAULT_ARGS, "retries": 0},
    schedule=None,
    start_date=START,
    catchup=False,
    max_active_runs=1,
    tags=TAGS + ["backfill", "ops"],
    params={
        "source": Param("transaction", type="string",
                        enum=sorted(CDC_SOURCES),
                        description="CDC source to re-load"),
        "from_ts": Param("1970-01-01 00:00:00", type="string",
                         description="Rewind the cursor to this timestamp (YYYY-MM-DD HH:MM:SS)"),
    },
) as dag:

    rewind = PythonOperator(task_id="rewind_cursor", python_callable=rewind_cursor)

    reload = PostgresToClickHouseOperator(
        task_id="reload_source",
        source="{{ params.source }}",
        batch_size=50_000,
    )

    rewind >> reload
