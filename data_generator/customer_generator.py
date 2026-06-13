"""Customer generator — demographics, hashed PII, device fingerprint and
risk profile. ~85% low-risk, with a small high-risk tail (some blacklisted)
that the fraud generator preferentially draws from.
"""
from __future__ import annotations

import hashlib
import random
import uuid
from dataclasses import dataclass, asdict

from reference import CITIES


@dataclass
class Customer:
    customer_id: str
    age_band: str
    gender: str
    home_city: str
    home_state: str
    phone_hash: str
    email_hash: str
    device_fingerprint: str
    kyc_level: str
    risk_profile: str            # low / medium / high
    preferred_method: str        # upi / card / wallet
    first_seen_date: str
    is_blacklisted: int


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def generate_customers(n: int, seed: int = 43) -> list[Customer]:
    rng = random.Random(seed)
    city_states = {c[0]: c[1] for c in CITIES}
    city_names = [c[0] for c in CITIES]
    city_weights = [c[4] for c in CITIES]
    customers: list[Customer] = []
    for _ in range(n):
        risk = rng.choices(["low", "medium", "high"], weights=[0.85, 0.12, 0.03])[0]
        cid = f"C{uuid.UUID(int=rng.getrandbits(128)).hex[:10].upper()}"
        home_city = rng.choices(city_names, weights=city_weights)[0]
        customers.append(Customer(
            customer_id=cid,
            age_band=rng.choices(["18-25", "26-35", "36-45", "46-60", "60+"],
                                 weights=[0.22, 0.34, 0.24, 0.14, 0.06])[0],
            gender=rng.choices(["M", "F", "O"], weights=[0.55, 0.43, 0.02])[0],
            home_city=home_city,
            home_state=city_states[home_city],
            phone_hash=_sha(f"ph-{cid}"),
            email_hash=_sha(f"em-{cid}") if rng.random() < 0.6 else "",
            device_fingerprint=_sha(f"fp-{cid}")[:16],
            kyc_level=rng.choices(["min", "full"], weights=[0.7, 0.3])[0],
            risk_profile=risk,
            preferred_method=rng.choices(["upi", "card", "wallet"], weights=[0.58, 0.30, 0.12])[0],
            first_seen_date=f"202{rng.randint(2, 5)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            is_blacklisted=int(risk == "high" and rng.random() < 0.1),
        ))
    return customers


def to_dicts(customers: list[Customer]) -> list[dict]:
    return [asdict(c) for c in customers]
