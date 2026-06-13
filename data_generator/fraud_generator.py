"""Fraud generator — turns a single (already-enriched) seed transaction into a
realistic fraud *burst* matching one of the modeled scenarios. Each emitted
event carries fraud_label=1 and the fraud_scenario tag, so downstream the
labels are exact for training and the dashboards.

The scenarios and their feature signatures are documented in
docs/domain/fraud_flow.md. This module is pure functions — the transaction
generator supplies a `reissue` callback that clones the seed with fresh switch
identifiers (RRN/STAN/auth code) so every burst event is a distinct
authorization while staying correlated on card/device/merchant.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Callable

from reference import FRAUD_SCENARIO_WEIGHTS, pick

# A reissue clones a seed txn at a new timestamp with fresh identifiers.
ReissueFn = Callable[[dict, datetime], dict]


def inject_fraud(rng: random.Random, seed_txn: dict, ts: datetime,
                 reissue: ReissueFn, city_coords: list[tuple[float, float]]) -> list[dict]:
    """Return the full list of transactions for one fraud incident.

    `seed_txn` is a freshly-enriched base transaction; we mark it fraudulent,
    choose a scenario, and expand it into the burst that scenario produces.
    """
    scenario = pick(rng, FRAUD_SCENARIO_WEIGHTS)
    seed_txn["fraud_label"] = 1
    seed_txn["fraud_scenario"] = scenario
    burst = [seed_txn]

    if scenario == "velocity":
        # 5-15 rapid auths on the same instrument within minutes.
        for i in range(rng.randint(5, 15)):
            t = reissue(seed_txn, ts + timedelta(seconds=rng.randint(10, 280) * (i + 1) // 3))
            t["amount"] = round(seed_txn["amount"] * rng.uniform(0.8, 1.2), 2)
            burst.append(t)

    elif scenario == "card_testing":
        # 10-30 tiny-amount probes with a high decline ratio (~70%).
        for i in range(rng.randint(10, 30)):
            t = reissue(seed_txn, ts + timedelta(seconds=i * rng.randint(3, 20)))
            t["amount"] = round(rng.uniform(1, 50), 2)
            declined = rng.random() < 0.7
            t["response_code"] = "05" if declined else "00"
            t["response_message"] = "DO NOT HONOR" if declined else "APPROVED"
            t["is_success"] = int(not declined)
            t["cvv_result"] = "N" if declined else "M"
            burst.append(t)

    elif scenario in ("device_takeover", "geo_anomaly"):
        # Same instrument transacting from a far-away geo at inflated amounts.
        far_city = rng.choice(city_coords)
        for t in burst:
            t["latitude"], t["longitude"] = far_city
            t["amount"] = round(t["amount"] * rng.uniform(3, 8), 2)

    elif scenario == "merchant_collusion":
        # Inflated tickets run at odd hours (2-4 AM) — laundering / cash-out.
        odd_hour = ts.replace(hour=rng.choice([2, 3, 4]))
        for i in range(rng.randint(3, 8)):
            t = reissue(seed_txn, odd_hour + timedelta(minutes=i * rng.randint(2, 10)))
            t["amount"] = round(seed_txn["amount"] * rng.uniform(8, 20), 2)
            burst.append(t)

    # refund_abuse: the purchase itself looks normal; the abuse surfaces as a
    # rapid refund to a different instrument (emitted by refund_generator when
    # it sees fraud_scenario == 'refund_abuse').
    return burst
