"""Model factory — the three fraud classifiers. XGBoost and LightGBM are
imported lazily; if a library is absent the model is skipped (so the pipeline
runs anywhere — RandomForest from sklearn is always available, the container
ships all three). Class imbalance (~fraud is rare) is handled per-model:
RF/LGBM via class_weight='balanced', XGB via scale_pos_weight.
"""
from __future__ import annotations

from sklearn.ensemble import RandomForestClassifier

from ml.config import RANDOM_STATE


def build_models(scale_pos_weight: float = 1.0) -> dict:
    """Return {name: estimator} for every available library."""
    models: dict[str, object] = {
        "random_forest": RandomForestClassifier(
            n_estimators=200, max_depth=12, min_samples_leaf=20,
            class_weight="balanced", n_jobs=-1, random_state=RANDOM_STATE,
        ),
    }

    try:
        from xgboost import XGBClassifier
        models["xgboost"] = XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.1,
            subsample=0.8, colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight, eval_metric="aucpr",
            tree_method="hist", random_state=RANDOM_STATE, n_jobs=-1,
        )
    except ImportError:
        pass

    try:
        from lightgbm import LGBMClassifier
        models["lightgbm"] = LGBMClassifier(
            n_estimators=300, num_leaves=31, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1, verbose=-1,
        )
    except ImportError:
        pass

    return models
