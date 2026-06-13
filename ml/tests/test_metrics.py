"""Metrics + model-factory tests (no ClickHouse / no MLflow needed)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
from ml.evaluation.metrics import compute  # noqa: E402
from ml.training.models import build_models  # noqa: E402


def test_perfect_separation():
    y = [0, 0, 1, 1]
    p = [0.01, 0.02, 0.98, 0.99]
    m = compute(y, p)
    assert m["precision"] == 1.0 and m["recall"] == 1.0 and m["f1"] == 1.0
    assert m["roc_auc"] == 1.0 and m["pr_auc"] == 1.0
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (2, 0, 0, 2)


def test_all_negative_predictions():
    y = [0, 0, 0, 1]
    p = [0.1, 0.1, 0.1, 0.2]      # below 0.5 -> all predicted negative
    m = compute(y, p, threshold=0.5)
    assert m["recall"] == 0.0 and m["positives"] == 1


def test_metric_keys_present():
    m = compute([0, 1], [0.2, 0.8])
    for k in ("precision", "recall", "f1", "roc_auc", "pr_auc", "tp", "fp", "fn", "tn"):
        assert k in m


def test_factory_has_random_forest():
    models = build_models(scale_pos_weight=10.0)
    assert "random_forest" in models          # always available
    assert all(hasattr(m, "fit") for m in models.values())


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} ML tests passed (models available: "
          f"{sorted(build_models(1.0))})")
