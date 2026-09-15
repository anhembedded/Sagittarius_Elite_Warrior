"""`EPIC-021A` — only a **session factory** may construct `binance.client.Client`.

@details The rule and its two allowed files, in that order, because the count
changed and the rule did not. `EPIC-021A` wrote it as "one file", and for four
pull requests that file was `ExchangeSessionFactory` — one class implementing
two contexts' ports, which is exactly what `EPIC-025` PR 1.3c-4 split. The
point was never the number: it is that venue flags and credentials must not be
scattered across the app, so **only a session factory mints a session**. There
are two session factories now, one per bounded context, and both are named
below by exact path — no wildcard, no directory, so a third construction site
anywhere still fails this test.

What each may mint is not symmetric, and that asymmetry is the rule doing its
job: `MarketDataSessionFactory` can only build an unsigned public session (ADR
§2.1 — a market-data client holds no credentials), and
`FuturesSessionFactory` is the only place in the app that can build a signed
one.

Not a docstring claim: each factory's own module docstring says it is one of
the two places allowed to call `Client(...)`, and a
claim like that is worthless unless something breaks when it stops being true
(`architecture-rule.md` §7 — code must say what it means, not just
document it). This scans `src/` and `scripts/` by `ast` for a **call**
`Client(...)` where the name resolves to `from binance.client import Client`
— not merely the import, since `client.py` legitimately imports `Client`
for its `client: Client` type annotation without ever constructing one.
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
    / "market_data"
    / "adapters"
    / "binance"
    / "market_data_session_factory.py",
    _REPO_ROOT
    / "src"
    / "modules"
    / "trading"
    / "adapters"
    / "binance"
    / "futures_session_factory.py",
]


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


def test_only_a_session_factory_constructs_binance_client() -> None:
    hits = _files_constructing_binance_client()
    assert hits == sorted(_ALLOWED_FILES), (
        "binance.client.Client() constructed outside the two session "
        "factories: "
        f"{[str(p.relative_to(_REPO_ROOT)) for p in hits if p not in _ALLOWED_FILES]}"
    )


def test_the_allowed_set_is_exact_and_not_a_directory() -> None:
    """The count went from one file to two in PR 1.3c-4, so this pins what did
    NOT change: every allowed path is a file, named in full. A directory or a
    glob here would let the next adapter in either module mint its own session
    and this test would keep passing."""
    assert all(path.suffix == ".py" and path.is_file() for path in _ALLOWED_FILES)
    assert len(_ALLOWED_FILES) == len(set(_ALLOWED_FILES))


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
