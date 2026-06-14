"""Unit tests for the ML plane — no ClickHouse / MLflow needed.

Covers the evaluation metrics (the numbers that gate model promotion), the
model factory, and the shape/correctness of the velocity feature SQL that
training and serving share.
"""
from __future__ import annotations

import numpy as np
import pytest

pytestmark = pytest.mark.unit


# -------------------------------- metrics ------------------------------------
def test_perfect_separation_scores_one():
    from ml.evaluation.metrics import compute
    m = compute([0, 0, 1, 1], [0.01, 0.02, 0.98, 0.99])
    assert m["precision"] == 1.0 and m["recall"] == 1.0 and m["f1"] == 1.0
    assert m["roc_auc"] == 1.0 and m["pr_auc"] == 1.0
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (2, 0, 0, 2)


def test_threshold_changes_confusion_matrix():
    from ml.evaluation.metrics import compute
    y = [0, 0, 0, 1]
    p = [0.1, 0.1, 0.1, 0.2]
    strict = compute(y, p, threshold=0.5)   # nothing predicted positive
    loose = compute(y, p, threshold=0.15)   # the 0.2 fires
    assert strict["recall"] == 0.0
    assert loose["recall"] == 1.0


def test_metrics_expose_promotion_key():
    """ml.config.PROMOTE_METRIC must exist in the metrics dict, else promotion
    selection silently breaks."""
    from ml.evaluation.metrics import compute
    from ml.config import PROMOTE_METRIC
    m = compute([0, 1, 0, 1], [0.2, 0.8, 0.3, 0.7])
    assert PROMOTE_METRIC in m


# ------------------------------ model factory --------------------------------
def test_build_models_always_has_random_forest():
    from ml.training.models import build_models
    models = build_models()
    assert "random_forest" in models  # sklearn always present


def test_build_models_trains_and_predicts_probabilities():
    """Whatever libraries are installed, every returned estimator must fit and
    emit calibrated [0,1] probabilities the scorer can band."""
    from ml.training.models import build_models
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 8))
    y = (X[:, 0] + rng.normal(scale=0.1, size=200) > 0).astype(int)
    for name, est in build_models(scale_pos_weight=1.0).items():
        est.fit(X, y)
        proba = est.predict_proba(X)[:, 1]
        assert proba.shape == (200,)
        assert proba.min() >= 0.0 and proba.max() <= 1.0, name


# ------------------------- velocity feature SQL ------------------------------
def test_training_sql_has_all_velocity_features_and_label():
    from ml.feature_engineering.velocity import training_sql
    from ml.config import FEATURE_COLUMNS
    sql = training_sql(sample=1000)
    for col in FEATURE_COLUMNS:
        assert col in sql, col
    assert "AS label" in sql
    assert "LIMIT 1000" in sql


def test_training_sql_uses_time_range_windows_for_leakage_safety():
    """RANGE BETWEEN N PRECEDING ... CURRENT ROW = true trailing time windows;
    ORDER BY ts lets the caller make a leakage-free time split."""
    from ml.feature_engineering.velocity import training_sql
    sql = training_sql(sample=10)
    assert "RANGE BETWEEN 300 PRECEDING AND CURRENT ROW" in sql
    assert "RANGE BETWEEN 86400 PRECEDING AND CURRENT ROW" in sql
    assert "ORDER BY ts" in sql


def test_training_sql_respects_db_override():
    from ml.feature_engineering.velocity import training_sql
    assert "warehouse2.fact_transactions" in training_sql(sample=5, db="warehouse2")
