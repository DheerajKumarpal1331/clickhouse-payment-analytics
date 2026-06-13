"""Device generator — POS terminals attached to merchants. Device count per
merchant comes from the merchant record (log-normal), so total devices scale
with the merchant base (~2-5 per merchant on average). Online merchants get
an e-com gateway instead of a physical terminal.
"""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, asdict

from reference import TERMINAL_TYPES, NETWORK_TYPES, FIRMWARE_VERSIONS, MANUFACTURERS
from merchant_generator import Merchant


@dataclass
class PosDevice:
    device_id: str
    merchant_id: str
    store_id: str
    terminal_id: str
    serial_number: str
    terminal_type: str
    manufacturer: str
    model: str
    os_version: str
    firmware_version: str
    app_version: str
    key_serial_number: str
    network_type: str
    sim_operator: str
    installed_date: str
    status: str


def generate_devices(merchants: list[Merchant], seed: int = 44) -> list[PosDevice]:
    rng = random.Random(seed)
    devices: list[PosDevice] = []
    for m in merchants:
        for slot in range(m.device_count):
            ttype = "ecom_gateway" if m.category == "online" else rng.choice(TERMINAL_TYPES[:4])
            mfg, model = MANUFACTURERS[ttype]
            did = f"D{uuid.UUID(int=rng.getrandbits(128)).hex[:10].upper()}"
            devices.append(PosDevice(
                device_id=did,
                merchant_id=m.merchant_id,
                store_id=f"S{m.merchant_id[-4:]}{slot % 3 + 1:02d}",
                terminal_id=f"{abs(hash(did)) % 10**8:08d}",
                serial_number=f"{mfg[:3].upper()}{rng.getrandbits(40):010X}",
                terminal_type=ttype,
                manufacturer=mfg,
                model=model,
                os_version=("android_13" if ttype == "android_smartpos" else
                            "linux_4.19" if ttype == "linux_pos" else ""),
                firmware_version=rng.choice(FIRMWARE_VERSIONS),
                app_version=rng.choice(["4.2.1", "4.3.0", "4.4.2"]),
                key_serial_number=f"FFFF{rng.getrandbits(60):015X}" if ttype != "soundbox_qr" else "",
                network_type=rng.choices(NETWORK_TYPES, weights=[0.5, 0.25, 0.15, 0.1])[0],
                sim_operator=rng.choice(["jio", "airtel", "vi", "bsnl"]),
                installed_date=m.onboarded_date,
                status=rng.choices(["active", "inactive", "faulty"], weights=[0.94, 0.04, 0.02])[0],
            ))
    return devices


def to_dicts(devices: list[PosDevice]) -> list[dict]:
    return [asdict(d) for d in devices]
