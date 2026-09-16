"""An interface class lives in an `i_*.py` file — rescued in PR 3.1c.

This rule used to be `test_application_layer_structure.py`'s third check,
scanning `src/application/ports/`. PR 1.3a emptied that directory and PR 3.1c
retargeted the guard onto `src/modules/*/application/`, where the rule has no
subject at all: a module's abstractions are its `contracts/`, and an `I*` class
under `application/` is now forbidden outright rather than merely misfiled.

Dropping the check with the directory would have been the quiet half of a
retarget — **a rule that stopped being checked reads exactly like a rule that
was obeyed** (`ci-rule.md` §5.5, and the reviewer's question J2). So the rule
moves to the address its subject moved to. Measured before writing it: 143 files
under a `contracts/` tree, 36 of them declaring an interface, and **zero**
offenders — the convention was already universal, which is what makes a ratchet
the right shape for it.

Why the naming matters beyond tidiness: `i_symbol_metadata_provider.py` tells a
reader which of two files beside each other is the contract and which the
implementation, and `BUG-127` was a whole feature wired to the wrong one of such
a pair. The file name is the cheapest available signal.

Pure static analysis (`ast`) — no PySide6, no database, no `qapp` fixture.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"

#: An interface name: `I` followed by an upper-case letter, so `IOrderSubmission`
#: matches and `Indicator` does not. Same expression as the guard this rule came
#: from, deliberately — two spellings of one rule drift.
_INTERFACE_NAME = re.compile(r"^I[A-Z]")


def _contract_files() -> list[Path]:
    """Every `.py` under any `contracts/` tree in `src/` — modules and support
    packages alike. Not restricted to `modules/`: `support/binance_gateway` and
    `support/charting` publish ports too, and the convention is the repository's
    rather than one tree's."""
    return sorted(
        p for p in _SRC_ROOT.rglob("contracts/**/*.py") if "__pycache__" not in p.parts
    )


def _interface_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and _INTERFACE_NAME.match(node.name)
    ]


def test_the_guard_has_a_subject() -> None:
    """A path-scanning guard whose tree has moved passes faster rather than
    failing, which is the failure this rule was itself rescued from. Locked at
    "more than fifty", because the count grows with every phase."""
    files = _contract_files()

    assert len(files) > 50, (
        f"only {len(files)} file(s) under a contracts/ tree in src/. Either the "
        "contracts moved, or this guard is reading nothing and would pass on "
        "anything."
    )

    declaring = [p for p in files if _interface_names(p)]
    assert len(declaring) > 20, (
        f"only {len(declaring)} contract file(s) declare an interface at all; "
        "the rule below would then be checking almost nothing."
    )


def test_an_interface_in_contracts_lives_in_an_i_prefixed_file() -> None:
    offenders = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}: {', '.join(names)}"
        for path in _contract_files()
        if (names := _interface_names(path)) and not path.stem.startswith("i_")
    ]

    assert offenders == [], (
        "a file declaring an interface class under `contracts/` must be named "
        "`i_*.py`, so a reader can tell the contract from its implementation "
        "without opening either:\n  " + "\n  ".join(offenders)
    )
