"""Merchant generator — produces the merchant master at acquirer width
(KYC, banking, per-method pricing, risk, lifecycle). Distribution is
calibrated to an Indian POS portfolio: tier-1/2 city skew, retail + food
dominant MCC mix, log-normal device counts (most merchants 1-2 terminals,
chains have many).
"""
from __future__ import annotations

import hashlib
import random
import uuid
from dataclasses import dataclass, asdict

from reference import BUSINESS_TYPES, CITIES, LEGAL_SUFFIXES, SETTLEMENT_BANKS


@dataclass
class Merchant:
    merchant_id: str
    legal_name: str
    dba_name: str
    business_type: str
    mcc: str
    category: str
    entity_type: str
    pan_hash: str
    gstin_masked: str
    kyc_status: str
    kyc_verified_date: str
    address_line: str
    city: str
    state: str
    pincode: str
    latitude: float
    longitude: float
    settlement_bank: str
    ifsc: str
    account_hash: str
    settlement_cycle: str
    hold_payouts: int
    mdr_card_credit_bps: int
    mdr_card_debit_bps: int
    mdr_upi_bps: int
    mdr_wallet_bps: int
    pricing_plan: str
    device_count: int
    avg_ticket: float
    expected_monthly_volume: float
    risk_score: float            # 0-1, drives fraud injection bias
    risk_tier: str
    is_high_volume: bool
    chargeback_threshold_bps: int
    onboarded_date: str
    activation_date: str
    status: str
    sales_channel: str
    relationship_manager: str
    parent_merchant_id: str


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _weighted_business(rng: random.Random) -> str:
    return rng.choices(list(BUSINESS_TYPES),
                       weights=[v["weight"] for v in BUSINESS_TYPES.values()])[0]


def generate_merchants(n: int, seed: int = 42) -> list[Merchant]:
    rng = random.Random(seed)
    rms = [f"RM{i:03d}" for i in range(1, 41)]
    merchants: list[Merchant] = []
    for i in range(n):
        btype = _weighted_business(rng)
        meta = BUSINESS_TYPES[btype]
        city, state, lat, lon, _ = rng.choices(CITIES, weights=[c[4] for c in CITIES])[0]
        device_count = max(1, int(rng.lognormvariate(0.3, 0.9)))
        avg_ticket = meta["avg_ticket"] * rng.uniform(0.6, 1.6)
        risk_score = round(min(1.0, max(0.0, rng.gauss(meta["risk_base"] * 10, 0.08))), 4)
        mid = f"M{uuid.UUID(int=rng.getrandbits(128)).hex[:10].upper()}"
        dba = f"{city} {btype.replace('_', ' ').title()} {i % 997}"
        onboarded = f"202{rng.randint(2, 5)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}"
        merchants.append(Merchant(
            merchant_id=mid,
            legal_name=f"{dba} {rng.choice(LEGAL_SUFFIXES)}",
            dba_name=dba,
            business_type=btype,
            mcc=meta["mcc"],
            category="offline" if btype != "ecommerce" else "online",
            entity_type=rng.choices(["proprietorship", "partnership", "pvt_ltd", "llp"],
                                    weights=[0.55, 0.15, 0.25, 0.05])[0],
            pan_hash=_sha(f"pan-{mid}"),
            gstin_masked=f"{rng.randint(10, 36)}XXXXX{rng.randint(1000, 9999)}X1Z{rng.randint(0, 9)}",
            kyc_status=rng.choices(["verified", "pending", "rejected"], weights=[0.93, 0.05, 0.02])[0],
            kyc_verified_date=onboarded,
            address_line=f"{rng.randint(1, 999)}, {rng.choice(['MG Road', 'Main Bazaar', 'Sector ' + str(rng.randint(1, 60)), 'Station Road'])}",
            city=city, state=state,
            pincode=f"{rng.randint(110001, 855999)}",
            latitude=round(lat + rng.uniform(-0.05, 0.05), 6),
            longitude=round(lon + rng.uniform(-0.05, 0.05), 6),
            settlement_bank=rng.choice(SETTLEMENT_BANKS),
            ifsc=f"{rng.choice(SETTLEMENT_BANKS)[:4]}0{rng.randint(100000, 999999)}",
            account_hash=_sha(f"acct-{mid}"),
            settlement_cycle=rng.choices(["T+1", "T+0", "T+2"], weights=[0.8, 0.1, 0.1])[0],
            hold_payouts=int(risk_score > 0.8),
            mdr_card_credit_bps=rng.choice([150, 165, 180, 200]),
            mdr_card_debit_bps=rng.choice([30, 40, 50]),
            mdr_upi_bps=0,
            mdr_wallet_bps=rng.choice([120, 150, 180]),
            pricing_plan=rng.choices(["standard", "enterprise", "promo"], weights=[0.7, 0.15, 0.15])[0],
            device_count=device_count,
            avg_ticket=avg_ticket,
            expected_monthly_volume=round(avg_ticket * device_count * rng.uniform(300, 1500), 2),
            risk_score=risk_score,
            risk_tier="high" if risk_score > 0.6 else "medium" if risk_score > 0.3 else "low",
            is_high_volume=device_count >= 5,
            chargeback_threshold_bps=100,
            onboarded_date=onboarded,
            activation_date=onboarded,
            status=rng.choices(["active", "dormant", "suspended"], weights=[0.9, 0.08, 0.02])[0],
            sales_channel=rng.choices(["field", "online", "partner"], weights=[0.6, 0.25, 0.15])[0],
            relationship_manager=rng.choice(rms) if device_count >= 5 else "",
            parent_merchant_id="",
        ))
    return merchants


def to_dicts(merchants: list[Merchant]) -> list[dict]:
    return [asdict(m) for m in merchants]
