"""fraud_training — scheduled retraining of the fraud-detection model (Phase 7).

Orchestration, not compute: the model is trained inside the project's
``fraud-training`` image (``python -m ml.train``), which logs runs and promotes
the winner to the MLflow registry. This DAG (1) gates on a freshly populated,
adequately *labeled* fact table so we never retrain on an empty or unlabeled
window, then (2) dispatches the training container.

Dispatch prefers the Docker API (the standard way Airflow runs a heavy,
differently-dependency'd job), falling back to a clear, logged handoff when the
Docker socket isn't mounted into the worker — so the DAG parses and runs
everywhere and the training contract stays explicit. Weekly, Monday 02:00 IST.
"""
from __future__ import annotations

import os

from airflow import DAG
from airflow.exceptions import AirflowSkipException
from airflow.operators.python import PythonOperator

from common import DB, DEFAULT_ARGS, START, TAGS
from operators.data_quality_operator import Check, DataQualityOperator
from sensors import ClickHousePartitionSensor

TRAIN_IMAGE = os.environ.get("TRAIN_IMAGE", "payments-fraud-training:latest")
TRAIN_CMD = os.environ.get("TRAIN_CMD", "python -m ml.train")
MIN_LABELED = int(os.environ.get("FRAUD_MIN_LABELED", "100"))


def dispatch_training(**context):
    """Run the training container via the Docker API; otherwise log the handoff."""
    env = {
        "CH_URL": os.environ.get("CH_URL", "http://analytics:analytics_secret@clickhouse:8123"),
        "MLFLOW_TRACKING_URI": os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000"),
    }
    try:
        import docker  # provided by the docker SDK when the socket is mounted
    except ImportError:
        raise AirflowSkipException(
            "Docker SDK unavailable in worker — mount /var/run/docker.sock and add "
            f"`docker` to run training automatically. Manual handoff: "
            f"`docker run --rm --network payments-net {TRAIN_IMAGE} {TRAIN_CMD}`")

    client = docker.from_env()
    print(f"Dispatching training: {TRAIN_IMAGE} :: {TRAIN_CMD}")
    logs = client.containers.run(
        TRAIN_IMAGE, command=TRAIN_CMD, environment=env,
        network="payments-net", remove=True, stdout=True, stderr=True,
    )
    out = logs.decode() if isinstance(logs, bytes) else str(logs)
    print(out[-4000:])          # tail the training log into the task log
    return "trained"


with DAG(
    dag_id="fraud_training",
    description="Retrain + register the fraud model (dispatches the ml training container)",
    default_args=DEFAULT_ARGS,
    schedule="0 2 * * 1",          # Mondays 02:00 IST
    start_date=START,
    catchup=False,
    max_active_runs=1,
    tags=TAGS + ["ml", "fraud"],
) as dag:

    wait_data = ClickHousePartitionSensor(
        task_id="wait_for_transactions",
        table=f"{DB}.fact_transactions",
        min_rows=MIN_LABELED,
        mode="reschedule",
        poke_interval=600,
        timeout=3600,
        soft_fail=True,
    )

    check_labels = DataQualityOperator(
        task_id="check_labeled_fraud_present",
        checks=[
            Check(
                name="labeled_fraud_rows",
                sql=f"SELECT count() FROM {DB}.fact_transactions WHERE fraud_label = 1",
                min_value=MIN_LABELED,
            ),
        ],
    )

    train = PythonOperator(task_id="dispatch_training", python_callable=dispatch_training)

    wait_data >> check_labels >> train
