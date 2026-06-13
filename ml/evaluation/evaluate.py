"""Evaluate a fitted model on a holdout set."""
from __future__ import annotations

import numpy as np

from ml.evaluation.metrics import compute


def predict_proba(model, X) -> np.ndarray:
    """Positive-class probability, robust to estimators without predict_proba."""
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]
    if hasattr(model, "decision_function"):
        d = model.decision_function(X)
        return 1.0 / (1.0 + np.exp(-d))
    return model.predict(X).astype(float)


def evaluate(model, X_test, y_test, threshold: float = 0.5) -> dict:
    return compute(y_test, predict_proba(model, X_test), threshold)
