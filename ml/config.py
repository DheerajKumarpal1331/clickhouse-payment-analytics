"""ML pipeline config (env-driven; matches docker/ml/.env.example)."""
from __future__ import annotations

import os

CH_URL = os.getenv("CH_URL", "http://analytics:analytics_secret@localhost:8123")
CH_DB = os.getenv("CH_DB", "payments")

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "file:./mlruns")
MLFLOW_EXPERIMENT = os.getenv("MLFLOW_EXPERIMENT", "fraud_detection")
MODEL_NAME = os.getenv("MODEL_NAME", "fraud_detector")          # registry name
PROMOTE_METRIC = os.getenv("PROMOTE_METRIC", "pr_auc")          # selection metric (imbalanced)

# Training data shape
TRAIN_SAMPLE = int(os.getenv("TRAIN_SAMPLE", "200000"))         # rows pulled from CH
TEST_FRACTION = float(os.getenv("TEST_FRACTION", "0.2"))        # time-based holdout
RANDOM_STATE = int(os.getenv("RANDOM_STATE", "42"))

# The feature columns the velocity query produces (label excluded).
FEATURE_COLUMNS = [
    "amount", "is_international",
    "cust_velocity_5m", "cust_velocity_1h", "cust_velocity_24h",
    "device_velocity_1h", "merchant_velocity_1h", "geo_velocity_kmph",
]
LABEL_COLUMN = "label"
