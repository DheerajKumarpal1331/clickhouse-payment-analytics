# Fraud Detection Platform (Phase 7)

Production ML pipeline: build velocity features from ClickHouse → train three
models → evaluate on a leakage-free time split → track in MLflow → register the
best to the model registry → serve the champion.

## Models

`random_forest` (sklearn), `xgboost`, `lightgbm`. XGBoost/LightGBM are imported
lazily — if absent the pipeline skips them and still runs RandomForest, so it
works on any box; the container ships all three. Imbalance handled per model
(RF/LGBM `class_weight='balanced'`, XGB `scale_pos_weight`).

## Velocity features (`feature_engineering/velocity.py`)

Computed per transaction in ClickHouse with time-RANGE window functions:

| Feature | Definition |
|---|---|
| `cust_velocity_5m / 1h / 24h` | customer's txn count in the trailing 5 min / 1 h / 24 h |
| `device_velocity_1h` | device's txn count in the trailing hour |
| `merchant_velocity_1h` | merchant's txn count in the trailing hour |
| `geo_velocity_kmph` | great-circle distance from the customer's previous txn ÷ elapsed hours (impossible-travel) |

Plus `amount`, `is_international`. The same definitions are served online by the
Phase-6 feature store (training/serving parity).

## Layout

```
ml/
├── feature_engineering/   velocity SQL + leakage-free time-split dataset
├── training/              model factory (xgb / lgbm / rf, imbalance-aware)
├── evaluation/            metrics (P/R/F1/ROC-AUC/PR-AUC), evaluate, SHAP explain
├── experiments/           experiment config + runner (fit/eval/log per model)
├── mlflow/                tracking (params/metrics/model) + registry promotion
├── train.py               entrypoint: dataset -> train -> track -> register best
└── serve.py               entrypoint: load Production model, /predict /health
```

## Run

```bash
pip install -r ml/requirements.txt
export CH_URL=http://analytics:analytics_secret@localhost:8123
export MLFLOW_TRACKING_URI=http://localhost:5000        # or file:./mlruns

python -m ml.train --sample 200000     # train, evaluate, log to MLflow, register best
python -m ml.serve                      # serve champion on :8500
```

Containerized: `fraud-training` (compose `ml` profile, `Dockerfile.train`) runs
`python -m ml.train`; `fraud-serving` runs `python -m ml.serve`. Selection metric
is **PR-AUC** (right for rare-positive fraud); ROC-AUC, precision, recall, F1
also tracked. The weekly retraining DAG (Airflow phase) calls `ml.train`.
