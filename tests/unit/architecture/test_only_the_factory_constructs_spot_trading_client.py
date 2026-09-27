"""`EPIC-027K` — only `SpotTradingClientFactory` may construct
`SpotTradingClient`.

@details Mirrors `test_only_the_factory_constructs_futures_trading_client.py`'s
shape exactly, for the Spot half of the same seam: scans by `ast` for a
**call** `SpotTradingClient(...)` where the name resolves to `from
Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_trading_client
import SpotTradingClient` — not merely the import, since a type annotation
or the class's own module legitimately reference the name without
constructing an instance.

`Retire when:` `SpotTradingClient` itself is deleted (superseded by a
venue-agnostic client the factory returns without naming a concrete class).
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCANNED_DIRS = (_REPO_ROOT / "src", _REPO_ROOT / "scripts")

_ALLOWED_FILES = [
    _REPO_ROOT
    / "src"
    / "modules"
    / "trading"
    / "adapters"
    / "binance"
    / "spot"
    / "spot_trading_client_factory.py",
]


def _constructs_spot_trading_client(source: str, filename: str) -> bool:
    """True if `source` both imports `SpotTradingClient` from its own module
    (no `as` alias — the only shape this repo uses) and calls it."""
    tree = ast.parse(source, filename=filename)
    imports_client = any(
        isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.endswith("spot_trading_client")
        and any(
            alias.name == "SpotTradingClient" and alias.asname is None
            for alias in node.names
        )
        for node in ast.walk(tree)
    )
    if not imports_client:
        return False
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "SpotTradingClient"
        for node in ast.walk(tree)
    )


def _files_constructing_spot_trading_client() -> list[Path]:
    hits: list[Path] = []
    for scanned_dir in _SCANNED_DIRS:
        for path in sorted(scanned_dir.rglob("*.py")):
            if _constructs_spot_trading_client(
                path.read_text(encoding="utf-8"), str(path)
            ):
                hits.append(path)
    return hits


def test_only_the_factory_constructs_spot_trading_client() -> None:
    hits = _files_constructing_spot_trading_client()
    assert hits == sorted(_ALLOWED_FILES), (
        "SpotTradingClient(...) constructed outside SpotTradingClientFactory: "
        f"{[str(p.relative_to(_REPO_ROOT)) for p in hits if p not in _ALLOWED_FILES]}"
    )


def test_the_allowed_set_is_exact_and_not_a_directory() -> None:
    """Pins the count at one, named in full — a directory or glob here would
    let a second adapter mint its own client and this test would keep
    passing."""
    assert all(path.suffix == ".py" and path.is_file() for path in _ALLOWED_FILES)
    assert len(_ALLOWED_FILES) == len(set(_ALLOWED_FILES))


def test_guard_actually_detects_a_violation() -> None:
    """Mutation-verify (`testing-rule.md` §2): prove the scanner fires on a
    real violation shape, and correctly ignores the import-only shape a type
    annotation legitimately uses."""
    assert _constructs_spot_trading_client(
        "from x.spot_trading_client import SpotTradingClient\n\n"
        "SpotTradingClient(a, b, c, d)\n",
        "<violation-fixture>",
    )
    assert not _constructs_spot_trading_client(
        "from x.spot_trading_client import SpotTradingClient\n\n\n"
        "def f(c: SpotTradingClient) -> None: ...\n",
        "<type-annotation-only-fixture>",
    )
