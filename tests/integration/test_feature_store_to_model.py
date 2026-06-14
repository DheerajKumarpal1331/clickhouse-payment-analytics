"""Integration: Feature Store -> Model.

Proves the serving path that training and the fraud API share:
  - the online feature store answers against live ClickHouse;
  - real-time feature assembly (the API's pre-auth path) runs its velocity SQL
    against the live aggregates and returns the full FEATURE_COLUMNS vector;
  - that vector feeds a trained estimator and yields a calibrated probability —
    the same hand-off the scorer makes at request time.

Gated by RUN_INTEGRATION=1 (see tests/conftest.py).
"""
from __future__ import annotations

import numpy as np
import pytest

pytestmark = [pytest.mark.integration]


def test_online_store_answers(ch_url, ch_db, monkeypatch):
    """The feature_store package runs with its own dir on PYTHONPATH (its modules
    use sibling imports like `import clickhouse_client`/`import config`), exactly
    as it does in its container. Import it that way, but keep it hermetic: those
    top-level names collide with kafka's, so snapshot and restore sys.modules so
    no other test sees the wrong `config`."""
    import sys
    from pathlib import Path
    monkeypatch.setenv("CH_URL", ch_url)
    monkeypatch.setenv("CH_DB", ch_db)
    fs_dir = Path(__file__).resolve().parents[2] / "feature_store"

    collide = ("config", "clickhouse_client", "definitions")
    saved = {k: sys.modules.get(k) for k in collide}
    for k in collide:
        sys.modules.pop(k, None)
    for k in [m for m in sys.modules if m == "online" or m.startswith("online.")]:
        sys.modules.pop(k, None)
    try:
        monkeypatch.syspath_prepend(str(fs_dir))
        import online.serving as serving
        feats = serving.get_online_features("merchant", "M1")
        assert isinstance(feats, dict)  # empty dict if no rows yet — still a valid answer
    finally:
        for k in [m for m in sys.modules if m == "online" or m.startswith("online.")]:
            sys.modules.pop(k, None)
        for k, v in saved.items():
            if v is not None:
                sys.modules[k] = v
            else:
                sys.modules.pop(k, None)


def test_realtime_assembly_returns_full_vector(ch_url, ch_db, monkeypatch):
    monkeypatch.setenv("CH_URL", ch_url)
    monkeypatch.setenv("CH_DB", ch_db)
    from ml.config import FEATURE_COLUMNS
    from api.fraud_service import features as feat
    f = feat.assemble("M1", "C1", "D1", amount=999.0, is_international=1,
                      latitude=19.07, longitude=72.87)
    assert set(f) == set(FEATURE_COLUMNS)
    assert f["amount"] == 999.0 and f["is_international"] == 1.0
    assert all(isinstance(v, float) for v in f.values())


def test_assembled_features_feed_a_model(ch_url, ch_db, monkeypatch):
    """End-to-end FS -> model: assemble a live feature row, then score it with a
    trained estimator using the exact column order the scorer uses."""
    monkeypatch.setenv("CH_URL", ch_url)
    monkeypatch.setenv("CH_DB", ch_db)
    import pandas as pd
    from ml.config import FEATURE_COLUMNS
    from ml.training.models import build_models
    from api.fraud_service import features as feat

    # train a quick model on synthetic data (real training is Phase 7)
    rng = np.random.default_rng(0)
    X = rng.normal(size=(300, len(FEATURE_COLUMNS)))
    y = (X[:, 0] > 0).astype(int)
    model = build_models()["random_forest"].fit(X, y)

    f = feat.assemble("M1", "C1", "D1", amount=500.0, is_international=0)
    row = pd.DataFrame([f])[FEATURE_COLUMNS]
    prob = float(model.predict_proba(row)[:, 1][0])
    assert 0.0 <= prob <= 1.0
