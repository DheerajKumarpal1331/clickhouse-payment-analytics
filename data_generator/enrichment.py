"""Processor-grade enrichment: fills the ISO 8583 / fee / EMV / 3DS /
settlement fields that a real switch stamps on every transaction.

Kept separate from transaction_generator.py so the core flow logic stays
readable; `enrich(txn, ...)` mutates the base dict in place and returns it.
"""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta

# Real-looking (but fake) BIN prefixes per network
BIN_RANGES = {
    "visa":       ["421323", "453278", "489537", "400123"],
    "mastercard": ["521478", "536123", "549876", "510987"],
    "rupay":      ["607432", "608123", "652876", "817612"],
    "amex":       ["371234", "376512"],
}
ISSUER_BANKS = ["HDFC", "ICICI", "SBI", "AXIS", "KOTAK", "IDFC", "YES", "PNB", "BOB", "CITI"]
ACQUIRERS = [("AQ001", "AXIS"), ("AQ002", "HDFC"), ("AQ003", "ICICI"), ("AQ004", "YES")]
RESPONSE_MESSAGES = {
    "00": "APPROVED", "51": "INSUFFICIENT FUNDS", "05": "DO NOT HONOR",
    "91": "ISSUER UNAVAILABLE", "54": "EXPIRED CARD", "61": "EXCEEDS LIMIT",
    "U69": "COLLECT REQUEST EXPIRED", "U30": "DEBIT FAILED",
}
ENTRY_MODES_BY_TERMINAL = {
    "android_smartpos": (["contactless", "chip", "swipe"], [0.55, 0.40, 0.05]),
    "linux_pos":        (["chip", "swipe", "contactless"], [0.60, 0.25, 0.15]),
    "mpos_dongle":      (["chip", "swipe"], [0.7, 0.3]),
    "soundbox_qr":      (["ecom"], [1.0]),
    "ecom_gateway":     (["ecom"], [1.0]),
}
EMV_AIDS = {"visa": "A0000000031010", "mastercard": "A0000000041010",
            "rupay": "A0000005241010", "amex": "A000000025010801"}
SIM_OPERATORS = ["jio", "airtel", "vi", "bsnl"]

# (mdr_bps_lookup) zero-MDR UPI per current RBI regime
MDR_BPS = {("card", "credit"): 180, ("card", "debit"): 40,
           ("upi", ""): 0, ("wallet", ""): 150, ("netbanking", ""): 90}


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def enrich(txn: dict, rng: random.Random, stan_counter: int,
           terminal_type: str, firmware: str, network_type: str,
           customer_fingerprint: str) -> dict:
    ts = datetime.strptime(txn["event_time"][:19], "%Y-%m-%d %H:%M:%S")
    method = txn["payment_method"]
    success = bool(txn["is_success"])
    amount = txn["amount"]

    # ── identifiers ──
    acq_id, acq_bank = rng.choice(ACQUIRERS)
    txn["rrn"] = f"{ts:%y%j}{stan_counter % 1_000_000:06d}{rng.randint(0, 9)}"
    txn["stan"] = stan_counter % 1_000_000
    txn["auth_code"] = f"{rng.randint(0, 999999):06d}" if success else "000000"
    txn["order_id"] = f"ORD{ts:%Y%m%d}{rng.getrandbits(32):08X}"
    txn["invoice_number"] = f"INV{rng.getrandbits(24):06X}"
    txn["parent_transaction_id"] = ""
    txn["gateway_txn_id"] = f"GW{rng.getrandbits(48):012X}"
    txn["acquirer_txn_id"] = f"{acq_id}{rng.getrandbits(40):010X}"
    txn["network_txn_id"] = f"{rng.getrandbits(52):013X}" if method == "card" else ""
    txn["upi_txn_ref"] = f"{rng.randint(10**11, 10**12 - 1)}" if method == "upi" else ""
    txn["trace_id"] = f"{rng.getrandbits(64):016x}"
    txn["aggregator_id"] = ""
    txn["acquirer_id"] = acq_id
    txn["acquirer_bank"] = acq_bank
    txn["issuer_bank"] = rng.choice(ISSUER_BANKS)
    txn["issuer_country"] = "IN" if rng.random() < 0.97 else rng.choice(["US", "AE", "SG", "GB"])
    txn["sub_merchant_id"] = ""
    txn["store_id"] = f"S{txn['merchant_id'][-4:]}01"
    txn["terminal_id"] = f"{abs(hash(txn['device_id'])) % 10**8:08d}"

    # ── timestamps ──
    auth_ms = int(rng.lognormvariate(5.5, 0.6))           # ~250ms median issuer RTT
    txn["auth_time"] = (ts + timedelta(milliseconds=auth_ms)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    txn["capture_time"] = txn["auth_time"] if success else None
    txn["settlement_time"] = None
    txn["device_time"] = (ts + timedelta(seconds=rng.randint(-90, 90))
                          ).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # clock drift
    txn["auth_latency_ms"] = auth_ms

    # ── instrument detail ──
    if method == "card":
        network = txn.pop("card_type") or "visa"            # legacy field held network
        ctype = rng.choices(["credit", "debit", "prepaid"], weights=[0.35, 0.60, 0.05])[0]
        pan = rng.choice(BIN_RANGES[network]) + f"{rng.getrandbits(34) % 10**10:010d}"
        txn["card_network"], txn["card_type"] = network, ctype
        txn["card_bin"], txn["card_last4"] = pan[:6], pan[-4:]
        txn["card_hash"] = _hash(pan)
        txn["is_tokenized"] = int(rng.random() < 0.65)
        txn["token_requestor_id"] = f"TR{rng.randint(10**7, 10**8 - 1)}" if txn["is_tokenized"] else ""
        txn["emi_flag"] = int(amount > 8000 and rng.random() < 0.12)
        txn["emi_tenure_months"] = rng.choice([3, 6, 9, 12]) if txn["emi_flag"] else 0
        entry_modes, w = ENTRY_MODES_BY_TERMINAL.get(terminal_type, (["ecom"], [1.0]))
        txn["pos_entry_mode"] = rng.choices(entry_modes, weights=w)[0]
        cp = txn["pos_entry_mode"] in ("chip", "contactless", "swipe")
        txn["emv_aid"] = EMV_AIDS[network] if cp and txn["pos_entry_mode"] != "swipe" else ""
        txn["emv_tvr"] = f"{rng.getrandbits(40):010X}" if txn["emv_aid"] else ""
        txn["emv_tsi"] = "E800" if txn["emv_aid"] else ""
        txn["cvm_method"] = ("pin" if amount > 5000 or txn["pos_entry_mode"] == "chip"
                             else rng.choice(["cdcvm", "none"])) if cp else ""
        txn["fallback_flag"] = int(txn["pos_entry_mode"] == "swipe" and rng.random() < 0.3)
        txn["three_ds_version"] = rng.choice(["2.1", "2.2"]) if not cp else ""
        txn["three_ds_eci"] = ("05" if success else "07") if not cp else ""
        txn["three_ds_status"] = ("Y" if success else rng.choice(["N", "U"])) if not cp else ""
        txn["avs_result"] = rng.choice(["Y", "Z", "N"]) if not cp else ""
        txn["cvv_result"] = "M" if success else rng.choice(["M", "N"])
        mdr_key = ("card", ctype if ctype != "prepaid" else "debit")
    else:
        txn["card_network"] = txn["card_type"] = ""
        txn["card_bin"] = txn["card_last4"] = txn["card_hash"] = ""
        txn["is_tokenized"] = txn["emi_flag"] = txn["emi_tenure_months"] = 0
        txn["token_requestor_id"] = ""
        txn["pos_entry_mode"] = "ecom" if method != "upi" else rng.choices(
            ["qr", "intent", "collect"], weights=[0.5, 0.4, 0.1])[0]
        txn["emv_aid"] = txn["emv_tvr"] = txn["emv_tsi"] = txn["cvm_method"] = ""
        txn["fallback_flag"] = 0
        txn["three_ds_version"] = txn["three_ds_eci"] = txn["three_ds_status"] = ""
        txn["avs_result"] = txn["cvv_result"] = ""
        mdr_key = (method, "")
    txn["upi_flow"] = txn["pos_entry_mode"] if method == "upi" else ""
    if method == "upi":
        txn["pos_entry_mode"] = "ecom"
        vpa_user = f"{txn['customer_id'][:6].lower()}xxx"
        txn["payer_vpa"] = f"{vpa_user}@{txn['upi_provider'][:5]}"
        txn["payee_vpa"] = f"{txn['merchant_id'].lower()}@{txn['acquirer_bank'].lower()}"
    else:
        txn["payer_vpa"] = txn["payee_vpa"] = ""
    txn["wallet_provider"] = rng.choice(["paytm", "mobikwik", "amazonpay"]) if method == "wallet" else ""
    txn["netbanking_bank"] = rng.choice(ISSUER_BANKS) if method == "netbanking" else ""
    txn["card_issuer_country"] = txn["issuer_country"]
    txn["is_international"] = int(txn["issuer_country"] != "IN")

    # ── amounts & fees ──
    tip = round(amount * rng.uniform(0.05, 0.12), 2) if (
        txn.get("fraud_label") == 0 and rng.random() < 0.06) else 0.0
    txn["base_amount"] = amount
    txn["amount"] = round(amount + tip, 2)
    txn["tip_amount"] = tip
    txn["cashback_amount"] = 0.0
    txn["tax_amount"] = 0.0
    txn["convenience_fee"] = round(amount * 0.01, 2) if method == "netbanking" else 0.0
    txn["fx_rate"] = 1.0 if not txn["is_international"] else round(rng.uniform(74, 90), 4)
    mdr_bps = MDR_BPS.get(mdr_key, 90)
    mdr = round(txn["amount"] * mdr_bps / 10_000, 4) if success else 0.0
    txn["mdr_rate_bps"] = mdr_bps
    txn["mdr_amount"] = mdr
    txn["interchange_fee"] = round(mdr * 0.7, 4)            # interchange ≈ 70% of MDR
    txn["network_fee"] = round(mdr * 0.1, 4)
    txn["gst_on_fees"] = round(mdr * 0.18, 4)
    txn["net_settlement_amount"] = round(txn["amount"] - mdr - txn["gst_on_fees"], 2) if success else 0.0

    # ── auth / settlement / channel ──
    txn["response_message"] = RESPONSE_MESSAGES.get(txn["response_code"], "UNKNOWN")
    txn["retry_count"] = rng.choices([0, 1, 2], weights=[0.92, 0.06, 0.02])[0]
    txn["capture_mode"] = "auto"
    txn["settlement_status"] = "pending" if success else "na"
    txn["settlement_batch_id"] = ""
    txn["settlement_cycle"] = "T+1"
    txn["settlement_utr"] = ""
    txn["channel"] = ("ecom" if terminal_type == "ecom_gateway"
                      else "qr" if terminal_type == "soundbox_qr" else "pos")
    txn["product_code"] = "P2M"
    txn["is_recurring"] = int(rng.random() < 0.03)

    # ── device / network telemetry ──
    txn["firmware_version"] = firmware
    txn["app_version"] = rng.choice(["4.2.1", "4.3.0", "4.4.2"])
    txn["sdk_version"] = rng.choice(["1.9.0", "2.0.1", "2.1.0"])
    txn["network_type"] = network_type
    txn["sim_operator"] = rng.choice(SIM_OPERATORS) if network_type in ("4g", "2g") else ""
    txn["ip_address"] = f"10.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,254)}"
    txn["device_fingerprint"] = customer_fingerprint
    txn["user_agent"] = "" if txn["channel"] == "pos" else (
        "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120 Mobile")
    txn["battery_level"] = rng.randint(15, 100) if txn["channel"] == "pos" else 0
    txn["geo_accuracy_m"] = rng.choice([5, 10, 20, 50, 100])
    txn["pincode"] = f"{rng.randint(110001, 855999)}"
    txn["country"] = "IN"

    # ── risk / lineage ──
    txn["gateway_risk_score"] = round(min(1.0, max(0.0, rng.gauss(
        0.6 if txn.get("fraud_label") else 0.12, 0.1))), 4)
    txn["schema_version"] = 2
    txn["source_system"] = "switch" if txn["channel"] == "pos" else "gateway"
    return txn
