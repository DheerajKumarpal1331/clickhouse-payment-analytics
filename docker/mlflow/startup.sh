#!/usr/bin/env bash
# MLflow tracking server. The experiment-tracking and model-registry tables
# are auto-migrated into the backend store (Postgres `mlflow` db) on startup,
# satisfying the "experiment registry + model registry" IaC requirement.
set -e

exec mlflow server \
  --backend-store-uri "${MLFLOW_BACKEND_URI}" \
  --artifacts-destination "${MLFLOW_ARTIFACT_ROOT:-/mlflow/artifacts}" \
  --serve-artifacts \
  --host 0.0.0.0 --port 5000
