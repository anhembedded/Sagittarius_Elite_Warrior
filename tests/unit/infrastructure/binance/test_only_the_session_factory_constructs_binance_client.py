"""`EPIC-021A` — `ExchangeSessionFactory` must be the only place in the app
that can construct `binance.client.Client`.

@details Not a docstring claim: `exchange_session_factory.py`'s own module
docstring says "the one place... allowed to call `Client(...)`", and a claim
like that is worthless unless something breaks when it stops being true
(`architecture-rule.md` §7 — code must say what it means, not just
document it). This scans `src/` and `scripts/` by `ast` for a **call**
`Client(...)` where the name resolves to `from binance.client import Client`
— not merely the import, since `client.py` legitimately imports `Client`
for its `client: Client` type annotation without ever constructing one.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_SCANNED_DIRS = (_REPO_ROOT / "src", _REPO_ROOT / "scripts")

_ALLOWED_FILE = (
    _REPO_ROOT / "src" / "infrastructure" / "binance" / "exchange_session_factory.py"
)


def _constructs_binance_client(source: str, filename: str) -> bool:
    """True if `source` both imports `binance.client.Client` under the name
    `Client` (no `as` alias — the only shape this repo uses) and calls it."""
    tree = ast.parse(source, filename=filename)
    imports_client = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "binance.client"
        and any(alias.name == "Client" and alias.asname is None for alias in node.names)
        for node in ast.walk(tree)
    )
    if not imports_client:
        return False
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Client"
        for node in ast.walk(tree)
    )


def _files_constructing_binance_client() -> list[Path]:
    hits: list[Path] = []
    for scanned_dir in _SCANNED_DIRS:
        for path in sorted(scanned_dir.rglob("*.py")):
            if _constructs_binance_client(path.read_text(encoding="utf-8"), str(path)):
                hits.append(path)
    return hits


def test_only_exchange_session_factory_constructs_binance_client() -> None:
    hits = _files_constructing_binance_client()
    assert hits == [_ALLOWED_FILE], (
        f"binance.client.Client() constructed outside ExchangeSessionFactory: "
        f"{[str(p.relative_to(_REPO_ROOT)) for p in hits if p != _ALLOWED_FILE]}"
    )


def test_guard_actually_detects_a_violation() -> None:
    """Mutation-verify (`testing-rule.md` §2): prove the scanner fires on a
    real violation shape, not just on the current (clean) tree — and that it
    correctly ignores the import-only shape `client.py` legitimately uses."""
    assert _constructs_binance_client(
        "from binance.client import Client\n\nClient()\n", "<violation-fixture>"
    )
    assert not _constructs_binance_client(
        "from binance.client import Client\n\n\ndef f(c: Client) -> None: ...\n",
        "<type-annotation-only-fixture>",
    )
