"""Validation gate shared by producer and consumer. Returns a typed result so
callers route cleanly: valid -> publish/insert, invalid -> DLQ (never crash).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from pydantic import ValidationError

from .topics import TOPICS


@dataclass
class Result:
    ok: bool
    payload: dict | None = None    # validated dict (model_dump) when ok
    error: str | None = None       # human-readable reason when not ok


def validate(topic: str, raw: bytes | str | dict) -> Result:
    spec = TOPICS.get(topic)
    if spec is None:
        return Result(False, error=f"unknown topic: {topic}")
    try:
        data = raw if isinstance(raw, dict) else json.loads(raw)
    except (ValueError, TypeError) as e:
        return Result(False, error=f"json decode: {e}")
    try:
        model = spec.schema(**data)
    except ValidationError as e:
        return Result(False, error=f"schema: {e.errors(include_url=False)[:3]}")
    return Result(True, payload=model.model_dump())
