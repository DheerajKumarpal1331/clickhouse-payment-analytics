"""SHAP explainability — global feature importance + per-prediction reason
codes for the fraud dashboard / API. SHAP is optional (heavy); guarded so the
training pipeline runs without it.
"""
from __future__ import annotations

import numpy as np


def available() -> bool:
    try:
        import shap  # noqa: F401
        return True
    except ImportError:
        return False


def global_importance(model, X, feature_names: list[str]) -> dict[str, float]:
    """Mean |SHAP| per feature (tree models). Falls back to the model's native
    feature_importances_ if SHAP isn't installed."""
    if available():
        import shap
        expl = shap.TreeExplainer(model)
        vals = expl.shap_values(X)
        if isinstance(vals, list):          # some versions return per-class
            vals = vals[-1]
        imp = np.abs(vals).mean(axis=0)
        return dict(sorted(zip(feature_names, map(float, imp)), key=lambda kv: -kv[1]))
    if hasattr(model, "feature_importances_"):
        imp = model.feature_importances_
        return dict(sorted(zip(feature_names, map(float, imp)), key=lambda kv: -kv[1]))
    return {}


def reason_codes(model, x_row, feature_names: list[str], top_k: int = 3) -> list[str]:
    """Top contributing features for a single prediction (per-txn explanation)."""
    if not available():
        return []
    import shap
    expl = shap.TreeExplainer(model)
    vals = expl.shap_values(x_row)
    if isinstance(vals, list):
        vals = vals[-1]
    contrib = sorted(zip(feature_names, np.ravel(vals)), key=lambda kv: -abs(kv[1]))
    return [f for f, _ in contrib[:top_k]]
