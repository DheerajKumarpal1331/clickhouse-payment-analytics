"""MLflow tracking helpers. If mlflow isn't installed (local dev without it),
these degrade to no-ops so the pipeline still trains and prints metrics.
Note: `import mlflow` here resolves to the installed library, not this
ml.mlflow subpackage (Python 3 absolute imports).
"""
from __future__ import annotations

import contextlib

from ml.config import MLFLOW_EXPERIMENT, MLFLOW_TRACKING_URI

try:
    import mlflow
    AVAILABLE = True
except ImportError:
    mlflow = None
    AVAILABLE = False


def init() -> bool:
    if not AVAILABLE:
        print("[mlflow] not installed — tracking disabled (metrics still computed)")
        return False
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT)
    return True


@contextlib.contextmanager
def run(name: str):
    if AVAILABLE:
        with mlflow.start_run(run_name=name) as r:
            yield r
    else:
        yield None


def log_params(params: dict) -> None:
    if AVAILABLE:
        mlflow.log_params(params)


def log_metrics(metrics: dict) -> None:
    if AVAILABLE:
        # only numeric metrics
        mlflow.log_metrics({k: float(v) for k, v in metrics.items()
                            if isinstance(v, (int, float))})


def log_model(model, name: str, flavor: str):
    if not AVAILABLE:
        return None
    if flavor == "xgboost":
        import mlflow.xgboost as fl; fl.log_model(model, name)
    elif flavor == "lightgbm":
        import mlflow.lightgbm as fl; fl.log_model(model, name)
    else:
        import mlflow.sklearn as fl; fl.log_model(model, name)
