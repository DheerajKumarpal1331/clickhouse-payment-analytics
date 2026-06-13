"""Transaction generator — the core stream.

Temporal realism is produced by two-stage weighted sampling (fast at scale):
  1. pick a DAY  ∝ day_multiplier  (weekend, holiday, festive season, salary days)
  2. pick an HOUR ∝ HOURLY_CURVE   (lunch + evening peaks, pre-dawn trough)
Both use precomputed cumulative weights + bisect, so each draw is O(log n) and
the generator sustains millions of rows without per-call reweighting.

Merchant selection is Zipf-ish (high-volume merchants dominate) via the same
precomputed-cumulative + bisect trick. Fraud bursts are delegated to
fraud_generator; refunds/chargebacks to refund_generator.
"""
from __future__ import annotations

import bisect
import itertools
import math
import random
import uuid
from datetime import datetime, timedelta, time

from merchant_generator import Merchant
from customer_generator import Customer
from device_generator import PosDevice
from reference import (CARD_TYPES, HOURLY_CURVE, PAYMENT_METHODS, RESPONSE_CODES,
                       UPI_PROVIDERS, build_holidays, day_multiplier, pick)
from enrichment import enrich
from fraud_generator import inject_fraud


class TransactionGenerator:
    def __init__(self, merchants: list[Merchant], customers: list[Customer],
                 devices: list[PosDevice], fraud_rate: float = 0.004, seed: int = 7):
        self.rng = random.Random(seed)
        self.merchants = merchants
        self.customers = customers
        self.devices_by_merchant: dict[str, list[PosDevice]] = {}
        for d in devices:
            self.devices_by_merchant.setdefault(d.merchant_id, []).append(d)

        self.fraud_rate = fraud_rate
        self._stan = 0
        self._city_coords = list({(m.latitude, m.longitude) for m in merchants})

        # Precompute merchant cumulative weights (size^1.3 Zipf-ish bias).
        weights = [(m.device_count ** 1.3) * self.rng.uniform(0.5, 2.0) for m in merchants]
        self._merch_cum = list(itertools.accumulate(weights))
        self._merch_total = self._merch_cum[-1]

        # Precompute hour cumulative weights once.
        self._hour_cum = list(itertools.accumulate(HOURLY_CURVE))
        self._hour_total = self._hour_cum[-1]

    # ----------------------------------------------------------- pickers
    def _pick_merchant(self) -> Merchant:
        r = self.rng.random() * self._merch_total
        return self.merchants[bisect.bisect_right(self._merch_cum, r)]

    def _pick_hour(self) -> int:
        r = self.rng.random() * self._hour_total
        return bisect.bisect_right(self._hour_cum, r)

    # ------------------------------------------------------------ core txn
    def _base_txn(self, ts: datetime) -> dict:
        rng = self.rng
        merchant = self._pick_merchant()
        customer = self.customers[rng.randrange(len(self.customers))]
        device = rng.choice(self.devices_by_merchant[merchant.merchant_id])
        method = customer.preferred_method if rng.random() < 0.6 else pick(rng, PAYMENT_METHODS)
        amount = round(max(10.0, rng.lognormvariate(math.log(merchant.avg_ticket), 0.7)), 2)
        rc = pick(rng, {k: v[0] for k, v in RESPONSE_CODES.items()})
        success = RESPONSE_CODES[rc][1]
        txn = {
            "transaction_id": f"T{uuid.UUID(int=rng.getrandbits(128)).hex.upper()}",
            "merchant_id": merchant.merchant_id,
            "device_id": device.device_id,
            "customer_id": customer.customer_id,
            "event_time": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "amount": amount,
            "currency": "INR",
            "payment_method": method,
            "card_type": pick(rng, CARD_TYPES) if method == "card" else "",
            "upi_provider": pick(rng, UPI_PROVIDERS) if method == "upi" else "",
            "response_code": rc,
            "is_success": int(success),
            "settlement_status": "pending",
            "mcc": merchant.mcc,
            "city": merchant.city,
            "state": merchant.state,
            "latitude": merchant.latitude + rng.uniform(-0.01, 0.01),
            "longitude": merchant.longitude + rng.uniform(-0.01, 0.01),
            "fraud_label": 0,
            "fraud_scenario": "",
        }
        self._stan += 1
        return enrich(txn, rng, self._stan,
                      terminal_type=device.terminal_type,
                      firmware=device.firmware_version,
                      network_type=device.network_type,
                      customer_fingerprint=customer.device_fingerprint)

    def _reissue(self, txn: dict, ts: datetime) -> dict:
        """Clone a burst seed with fresh switch identifiers so the fraud
        pattern stays correlated while each event is a distinct auth."""
        rng = self.rng
        self._stan += 1
        t = dict(txn)
        t["transaction_id"] = f"T{uuid.UUID(int=rng.getrandbits(128)).hex.upper()}"
        t["event_time"] = ts.strftime("%Y-%m-%d %H:%M:%S")
        t["rrn"] = f"{ts:%y%j}{self._stan % 1_000_000:06d}{rng.randint(0, 9)}"
        t["stan"] = self._stan % 1_000_000
        t["auth_code"] = f"{rng.randint(0, 999999):06d}" if t["is_success"] else "000000"
        t["gateway_txn_id"] = f"GW{rng.getrandbits(48):012X}"
        t["acquirer_txn_id"] = t["acquirer_id"] + f"{rng.getrandbits(40):010X}"
        t["trace_id"] = f"{rng.getrandbits(64):016x}"
        t["order_id"] = f"ORD{ts:%Y%m%d}{rng.getrandbits(32):08X}"
        return t

    # -------------------------------------------------------------- stream
    def stream(self, start: datetime, end: datetime, target_count: int):
        """Yield ~target_count transactions in [start, end] with realistic
        day/hour shaping and injected fraud bursts."""
        rng = self.rng
        n_days = (end.date() - start.date()).days + 1
        days = [start.date() + timedelta(days=i) for i in range(n_days)]
        holidays = build_holidays(days[0].year, days[-1].year)
        day_w = [day_multiplier(d, holidays) for d in days]
        cum_days = list(itertools.accumulate(day_w))
        total_days = cum_days[-1]

        emitted = 0
        while emitted < target_count:
            d = days[bisect.bisect_right(cum_days, rng.random() * total_days)]
            ts = datetime.combine(d, time(self._pick_hour(), rng.randint(0, 59), rng.randint(0, 59)))

            if rng.random() < self.fraud_rate:
                seed = self._base_txn(ts)
                for t in inject_fraud(rng, seed, ts, self._reissue, self._city_coords):
                    yield t
                    emitted += 1
            else:
                yield self._base_txn(ts)
                emitted += 1
