"""Shared reference data and helpers for the synthetic payment ecosystem.

Centralizing constants here keeps the per-entity generators free of
cross-imports and makes the realism knobs (city mix, MCC behaviour, holiday
calendar, temporal curves) easy to find and tune.
"""
from __future__ import annotations

import random
from datetime import date

# ---------------------------------------------------------------- geography
# (city, state, lat, lon, portfolio weight)
CITIES = [
    ("Mumbai", "Maharashtra", 19.0760, 72.8777, 0.14),
    ("Delhi", "Delhi", 28.7041, 77.1025, 0.13),
    ("Bengaluru", "Karnataka", 12.9716, 77.5946, 0.12),
    ("Hyderabad", "Telangana", 17.3850, 78.4867, 0.08),
    ("Chennai", "Tamil Nadu", 13.0827, 80.2707, 0.07),
    ("Pune", "Maharashtra", 18.5204, 73.8567, 0.07),
    ("Kolkata", "West Bengal", 22.5726, 88.3639, 0.06),
    ("Ahmedabad", "Gujarat", 23.0225, 72.5714, 0.05),
    ("Jaipur", "Rajasthan", 26.9124, 75.7873, 0.04),
    ("Lucknow", "Uttar Pradesh", 26.8467, 80.9462, 0.04),
    ("Surat", "Gujarat", 21.1702, 72.8311, 0.03),
    ("Indore", "Madhya Pradesh", 22.7196, 75.8577, 0.03),
    ("Kochi", "Kerala", 9.9312, 76.2673, 0.03),
    ("Chandigarh", "Punjab", 30.7333, 76.7794, 0.03),
    ("Bhopal", "Madhya Pradesh", 23.2599, 77.4126, 0.02),
    ("Nagpur", "Maharashtra", 21.1458, 79.0882, 0.02),
    ("Coimbatore", "Tamil Nadu", 11.0168, 76.9558, 0.02),
    ("Visakhapatnam", "Andhra Pradesh", 17.6868, 83.2185, 0.02),
]

# ---------------------------------------------------------------- merchants
# business_type -> mcc, portfolio weight, avg ticket (INR), base risk
BUSINESS_TYPES = {
    "restaurant":   {"mcc": "5812", "weight": 0.18, "avg_ticket": 650,   "risk_base": 0.02},
    "grocery":      {"mcc": "5411", "weight": 0.22, "avg_ticket": 850,   "risk_base": 0.01},
    "hospital":     {"mcc": "8062", "weight": 0.05, "avg_ticket": 4200,  "risk_base": 0.01},
    "fuel_station": {"mcc": "5541", "weight": 0.12, "avg_ticket": 1500,  "risk_base": 0.015},
    "retail":       {"mcc": "5999", "weight": 0.20, "avg_ticket": 1100,  "risk_base": 0.02},
    "ecommerce":    {"mcc": "5969", "weight": 0.10, "avg_ticket": 1800,  "risk_base": 0.05},
    "pharmacy":     {"mcc": "5912", "weight": 0.08, "avg_ticket": 450,   "risk_base": 0.01},
    "electronics":  {"mcc": "5732", "weight": 0.05, "avg_ticket": 12000, "risk_base": 0.04},
}
LEGAL_SUFFIXES = ["Enterprises", "Traders", "& Sons", "Retail Pvt Ltd", "Stores", "Agencies"]
SETTLEMENT_BANKS = ["AXIS", "HDFC", "ICICI", "YES", "SBI"]

# ---------------------------------------------------------------- devices
TERMINAL_TYPES = ["android_smartpos", "linux_pos", "mpos_dongle", "soundbox_qr", "ecom_gateway"]
NETWORK_TYPES = ["4g", "wifi", "ethernet", "2g"]
FIRMWARE_VERSIONS = ["2.4.1", "2.5.0", "2.5.3", "3.0.1", "3.1.0"]
MANUFACTURERS = {
    "android_smartpos": ("pax", "A920"), "linux_pos": ("verifone", "V240m"),
    "mpos_dongle": ("newland", "ME31"), "soundbox_qr": ("inhouse", "SBX2"),
    "ecom_gateway": ("", ""),
}

# ---------------------------------------------------------------- payments
PAYMENT_METHODS = {"upi": 0.55, "card": 0.30, "wallet": 0.10, "netbanking": 0.05}
CARD_TYPES = {"visa": 0.35, "mastercard": 0.33, "rupay": 0.27, "amex": 0.05}
UPI_PROVIDERS = {"phonepe": 0.42, "googlepay": 0.34, "paytm": 0.13, "bhim": 0.04, "other": 0.07}

# response code -> (weight, success)
RESPONSE_CODES = {
    "00": (0.930, True),    # approved
    "51": (0.025, False),   # insufficient funds
    "05": (0.015, False),   # do not honor
    "91": (0.010, False),   # issuer unavailable
    "54": (0.005, False),   # expired card
    "61": (0.005, False),   # exceeds limit
    "U69": (0.008, False),  # UPI collect expired
    "U30": (0.002, False),  # UPI debit failed
}

# ---------------------------------------------------------------- temporal
# Relative volume by hour of day (lunch + evening peaks, 2-5 AM trough).
HOURLY_CURVE = [0.2, 0.1, 0.05, 0.05, 0.1, 0.3, 0.6, 1.0, 1.4, 1.6, 1.7, 1.9,
                2.2, 2.0, 1.6, 1.5, 1.6, 1.9, 2.3, 2.5, 2.2, 1.6, 1.0, 0.5]

# Fixed national holidays applied every year + festival (Diwali) windows.
_FIXED_HOLIDAYS = [(1, 1), (1, 26), (8, 15), (10, 2), (12, 25), (12, 31)]
_DIWALI = {2022: date(2022, 10, 24), 2023: date(2023, 11, 12),
           2024: date(2024, 10, 31), 2025: date(2025, 10, 21),
           2026: date(2026, 11, 8)}


def build_holidays(start_year: int, end_year: int) -> set[date]:
    """National holidays + a 3-day Diwali window for each year in range."""
    from datetime import timedelta
    out: set[date] = set()
    for y in range(start_year, end_year + 1):
        for m, d in _FIXED_HOLIDAYS:
            out.add(date(y, m, d))
        if y in _DIWALI:
            for off in (-1, 0, 1):
                out.add(_DIWALI[y] + timedelta(days=off))
    return out


def day_multiplier(d: date, holidays: set[date]) -> float:
    """Day-level volume multiplier encoding weekend, holiday, festive-season
    and **salary-day** spending patterns (Indian salaries land on the 1st;
    spending spikes days 1-5 and again at month-end)."""
    w = 1.0
    if d.weekday() >= 5:            # Sat/Sun portfolio uplift
        w *= 1.25
    if d in holidays:
        w *= 1.8
    if d.month in (10, 11):         # festive season (Dussehra/Diwali run-up)
        w *= 1.25
    dom = d.day
    if dom <= 3:                    # just-got-paid splurge
        w *= 1.40
    elif dom <= 5:
        w *= 1.20
    if dom >= 28:                   # end-of-month / some employers pay last day
        w *= 1.25
    return w


# ---------------------------------------------------------------- fraud
FRAUD_SCENARIO_WEIGHTS = {
    "velocity": 0.30, "card_testing": 0.25, "device_takeover": 0.15,
    "geo_anomaly": 0.15, "merchant_collusion": 0.10, "refund_abuse": 0.05,
}


# ---------------------------------------------------------------- helpers
def pick(rng: random.Random, table: dict) -> str:
    """Weighted choice over a {value: weight} mapping."""
    return rng.choices(list(table), weights=list(table.values()))[0]
