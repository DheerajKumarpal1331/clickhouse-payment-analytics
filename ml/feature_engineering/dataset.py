"""Assemble the training dataset from the velocity query into a leakage-free
time-split (train on earlier txns, test on later) — never a random split, which
would leak future behaviour into the past.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml import clickhouse_client as ch
from ml.config import FEATURE_COLUMNS, LABEL_COLUMN, TEST_FRACTION, TRAIN_SAMPLE
from ml.feature_engineering.velocity import training_sql


def load_frame(sample: int = TRAIN_SAMPLE) -> pd.DataFrame:
    rows = ch.query(training_sql(sample))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # JSONEachRow returns numbers already, but coerce defensively.
    for c in FEATURE_COLUMNS + [LABEL_COLUMN, "ts"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def time_split(df: pd.DataFrame, test_fraction: float = TEST_FRACTION):
    """Chronological split on ts. Returns (X_train, y_train, X_test, y_test)."""
    df = df.sort_values("ts").reset_index(drop=True)
    cut = int(len(df) * (1 - test_fraction))
    train, test = df.iloc[:cut], df.iloc[cut:]
    return (train[FEATURE_COLUMNS], train[LABEL_COLUMN].astype(int),
            test[FEATURE_COLUMNS], test[LABEL_COLUMN].astype(int))


def build_dataset(sample: int = TRAIN_SAMPLE):
    df = load_frame(sample)
    if df.empty:
        raise RuntimeError("no training rows returned — is fact_transactions populated?")
    X_tr, y_tr, X_te, y_te = time_split(df)
    pos = int(y_tr.sum()); neg = int(len(y_tr) - pos)
    meta = {
        "rows": len(df), "train": len(X_tr), "test": len(X_te),
        "train_fraud": pos, "train_fraud_rate": round(pos / max(len(y_tr), 1), 4),
        "scale_pos_weight": round(neg / max(pos, 1), 2),   # for XGBoost imbalance
    }
    return X_tr, y_tr, X_te, y_te, meta
