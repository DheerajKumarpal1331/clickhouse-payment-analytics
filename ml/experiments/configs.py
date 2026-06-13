"""Experiment configuration. One feature set ('velocity_v1') and the model
roster; extend with hyperparameter grids or alternative feature sets as new
experiments. Kept declarative so train.py / the runner stay generic.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ml.config import FEATURE_COLUMNS


@dataclass
class Experiment:
    name: str = "velocity_v1"
    feature_set: str = "velocity_v1"
    features: list[str] = field(default_factory=lambda: list(FEATURE_COLUMNS))
    threshold: float = 0.5
    # which models to run; empty means "all available from the factory"
    models: list[str] = field(default_factory=list)


DEFAULT = Experiment()
