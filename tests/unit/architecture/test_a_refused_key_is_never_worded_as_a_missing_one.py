"""`BUG-193` — no reader words an absent key by itself.

@details A mainnet key the exchange refuses resolves to no credentials, and every
reader then had its own sentence for that ("No Spot credentials configured",
"No key"): the Trading page, the history, the commission rates and the streams
told the owner the key was missing while it was stored and merely refused. The
sentence is now `ResolvedCredentials.absence` / `unusable_because`, which knows
the refusal. This guard fails on a string in `src/` that says "credentials
configured" anywhere else (docstrings and comments excepted), so a new reader
cannot bring the old wording back.

`Retire when:` the credentials port returns a single typed outcome (a key, a
missing key, a refused key) that no reader can flatten to `None`.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"
_HOME = Path("src/support/binance_gateway/contracts/i_exchange_credentials_provider.py")
_PHRASE = "credentials configured"


def _docstrings(tree: ast.AST) -> set[int]:
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                found.add(id(first.value))
    return found


def _offences(source: str, filename: str) -> list[int]:
    tree = ast.parse(source, filename=filename)
    docstrings = _docstrings(tree)
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and _PHRASE in node.value
        and id(node) not in docstrings
    ]


def test_only_the_credentials_contract_words_an_absent_key() -> None:
    offences = [
        f"{path.relative_to(_REPO_ROOT)}:{line}"
        for path in sorted(_SRC.rglob("*.py"))
        if path.relative_to(_REPO_ROOT) != _HOME
        for line in _offences(path.read_text(encoding="utf-8"), str(path))
    ]

    assert offences == [], (
        "word an absent key through ResolvedCredentials.absence/unusable_because: "
        + ", ".join(offences)
    )


def test_the_guard_sees_a_reader_that_words_it_by_itself() -> None:
    source = 'def f(symbol):\n    raise ValueError(f"{symbol}: no Spot credentials configured")\n'

    assert _offences(source, "reader.py") == [2]


def test_the_guard_leaves_docstrings_alone() -> None:
    source = 'def f():\n    """No credentials configured."""\n'

    assert _offences(source, "reader.py") == []
