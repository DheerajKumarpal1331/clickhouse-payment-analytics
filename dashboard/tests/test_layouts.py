"""Layout smoke tests (no ClickHouse needed). data.q() returns empty frames on
failure, so every page must still render a Dash component tree."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dashboard.executive import view as executive   # noqa: E402
from dashboard.merchant import view as merchant      # noqa: E402
from dashboard.fraud import view as fraud            # noqa: E402
from dashboard.settlement import view as settlement  # noqa: E402
from dashboard.support import view as support        # noqa: E402


def test_all_pages_render_without_data():
    # CH unreachable here -> empty frames -> pages must not raise.
    for name, mod in [("executive", executive), ("merchant", merchant), ("fraud", fraud),
                      ("settlement", settlement), ("support", support)]:
        comp = mod.layout(30)
        assert comp is not None and hasattr(comp, "children"), name


def test_app_imports_and_has_server():
    from dashboard.app import app, server, PAGES
    assert server is not None
    assert set(PAGES) == {"/", "/merchant", "/fraud", "/settlement", "/support"}


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} dashboard tests passed")
