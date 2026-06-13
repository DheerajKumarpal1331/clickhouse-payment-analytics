"""Experiment runner — fit each model, evaluate on the time holdout, log
params/metrics/model to MLflow, and return the comparison.
"""
from __future__ import annotations

import time

from ml.experiments.configs import Experiment
from ml.evaluation.evaluate import evaluate
from ml.mlflow import tracking
from ml.training.models import build_models


def run_experiment(exp: Experiment, X_tr, y_tr, X_te, y_te, meta: dict) -> list[dict]:
    models = build_models(scale_pos_weight=meta.get("scale_pos_weight", 1.0))
    if exp.models:
        models = {k: v for k, v in models.items() if k in exp.models}

    results = []
    for name, model in models.items():
        t0 = time.time()
        with tracking.run(f"{exp.name}:{name}") as r:
            model.fit(X_tr[exp.features], y_tr)
            metrics = evaluate(model, X_te[exp.features], y_te, exp.threshold)
            train_secs = round(time.time() - t0, 2)

            tracking.log_params({
                "model": name, "feature_set": exp.feature_set,
                "n_features": len(exp.features), "train_rows": meta["train"],
                "train_fraud_rate": meta["train_fraud_rate"], "threshold": exp.threshold,
            })
            tracking.log_metrics({**metrics, "train_seconds": train_secs})
            tracking.log_model(model, "model", flavor=name)

            run_id = getattr(getattr(r, "info", None), "run_id", None)
            model_uri = f"runs:/{run_id}/model" if run_id else None
            results.append({"name": name, "metrics": metrics, "model": model,
                            "run_id": run_id, "model_uri": model_uri, "train_seconds": train_secs})
            print(f"  {name:14s} PR-AUC={metrics['pr_auc']} ROC-AUC={metrics['roc_auc']} "
                  f"P={metrics['precision']} R={metrics['recall']} F1={metrics['f1']} ({train_secs}s)")
    return results
