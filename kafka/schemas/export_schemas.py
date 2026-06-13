"""Export JSON Schema for every topic (Pydantic -> JSON Schema). Use these to
register contracts in a Schema Registry or for cross-language consumers.

    python -m schemas.export_schemas ./schemas/jsonschema
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .topics import TOPICS


def main(out_dir: str = "./jsonschema") -> int:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, spec in TOPICS.items():
        schema = spec.schema.model_json_schema()
        (out / f"{name}.schema.json").write_text(json.dumps(schema, indent=2))
        print(f"wrote {name}.schema.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
