"""Fraud model training entrypoint (fraud-training container / on-demand / Airflow).

    python -m ml.train                       # full run, default sample
    python -m ml.train --sample 50000        # smaller pull for a quick run

Pipeline: build leakage-free velocity dataset from ClickHouse -> train XGBoost,
LightGBM, RandomForest -> evaluate (precision/recall/F1/ROC-AUC/PR-AUC) ->
track each in MLflow -> register the best (by PR-AUC) to the model registry.
"""
from __future__ import annotations

import argparse
import json

from ml.config import TRAIN_SAMPLE, PROMOTE_METRIC
from ml.experiments.configs import DEFAULT
from ml.experiments.runner import run_experiment
from ml.feature_engineering.dataset import build_dataset
from ml.mlflow import tracking, registry


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=TRAIN_SAMPLE)
    args = ap.parse_args()

    print(f"==> building dataset (sample={args.sample})")
    X_tr, y_tr, X_te, y_te, meta = build_dataset(args.sample)
    print(f"    rows={meta['rows']} train={meta['train']} test={meta['test']} "
          f"train_fraud_rate={meta['train_fraud_rate']} spw={meta['scale_pos_weight']}")

    tracking.init()
    print(f"==> training models (experiment={DEFAULT.name})")
    results = run_experiment(DEFAULT, X_tr, y_tr, X_te, y_te, meta)

    print("==> registry")
    best = registry.register_best(results)

    summary = {
        "dataset": meta,
        "models": {r["name"]: r["metrics"] for r in results},
        "best": {"name": best["name"], PROMOTE_METRIC: best["metrics"].get(PROMOTE_METRIC)} if best else None,
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
