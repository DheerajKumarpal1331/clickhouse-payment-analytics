"""Shared test fixtures + collection gating.

- Puts the repo root on sys.path so tests import the platform packages
  (`kafka`, `ml`, `api`, `feature_store`) the same way the apps do.
- Integration tests are skipped unless RUN_INTEGRATION=1 *and* the relevant
  service is configured, so the unit suite stays green on any laptop while the
  same files run for real against the Docker stack.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---- connection settings (match docker-compose / .env.dev defaults) ---------
PG_DSN = os.getenv("PG_DSN", "postgresql://payments:payments_secret@localhost:5432/payments")
CH_URL = os.getenv("CH_URL", "http://analytics:analytics_secret@localhost:8123")
CH_DB = os.getenv("CH_DB", "payments")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

_RUN_INTEGRATION = os.getenv("RUN_INTEGRATION") == "1"
_RUN_LOAD = os.getenv("RUN_LOAD") == "1"


def pytest_collection_modifyitems(config, items):
    """Skip integration/load tests unless explicitly enabled, so the unit suite
    runs everywhere with no services."""
    skip_int = pytest.mark.skip(reason="integration: set RUN_INTEGRATION=1 (needs Docker stack)")
    skip_load = pytest.mark.skip(reason="load: set RUN_LOAD=1 (throughput/concurrency benchmark)")
    for item in items:
        if "load" in item.keywords and not _RUN_LOAD:
            item.add_marker(skip_load)
        elif "integration" in item.keywords and not _RUN_INTEGRATION:
            item.add_marker(skip_int)


# ---- fixtures (only used by integration tests; lazy so unit runs need no infra)
@pytest.fixture(scope="session")
def pg_dsn() -> str:
    return PG_DSN


@pytest.fixture(scope="session")
def ch_url() -> str:
    return CH_URL


@pytest.fixture(scope="session")
def ch_db() -> str:
    return CH_DB


@pytest.fixture(scope="session")
def kafka_bootstrap() -> str:
    return KAFKA_BOOTSTRAP
