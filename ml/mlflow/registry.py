"""Model registry promotion: register the best run's model under MODEL_NAME and
move it to the Production stage. Champion/challenger by the configured metric
(PR-AUC). No-op if mlflow is absent.
"""
from __future__ import annotations

from ml.config import MODEL_NAME, PROMOTE_METRIC
from ml.mlflow import tracking


def register_best(results: list[dict]) -> dict | None:
    """results: [{name, metrics, run_id, model_uri}, ...] -> the promoted entry."""
    if not results:
        return None
    best = max(results, key=lambda r: (r["metrics"].get(PROMOTE_METRIC) or 0))
    if not tracking.AVAILABLE or not best.get("model_uri"):
        print(f"[registry] best model: {best['name']} "
              f"({PROMOTE_METRIC}={best['metrics'].get(PROMOTE_METRIC)}) "
              f"[mlflow disabled — not registered]")
        return best

    import mlflow
    try:
        mv = mlflow.register_model(best["model_uri"], MODEL_NAME)
        client = mlflow.tracking.MlflowClient()
        client.transition_model_version_stage(
            name=MODEL_NAME, version=mv.version, stage="Production",
            archive_existing_versions=True,
        )
        print(f"[registry] promoted {best['name']} -> {MODEL_NAME} v{mv.version} (Production)")
        best["registered_version"] = mv.version
    except Exception as e:
        # The file-store backend has no model registry — needs the DB-backed
        # MLflow server (the `mlflow` compose service). Tracking still logged.
        print(f"[registry] best model: {best['name']} "
              f"({PROMOTE_METRIC}={best['metrics'].get(PROMOTE_METRIC)}) "
              f"[registry unavailable: {type(e).__name__}]")
    return best
