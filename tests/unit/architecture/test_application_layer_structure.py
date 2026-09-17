"""Guards two Application-layer naming/placement conventions.

- **CQRS structure** (`architecture-rule.md` §5, ADR D2): every Command / Query /
  Handler class lives in a file named for its role — `command.py`, `query.py`,
  `handler.py` — one role per file.
- **Explicit abstractions** (`architecture-rule.md` §2.1): an interface class
  (`I` + uppercase, e.g. `IMarketDataRepository`) is a **contract**, and a
  module's contracts live in `contracts/`. An `I*` class under
  `application/` is a port hiding inside the layer that should be consuming it.

## It was retargeted in PR 3.1c, and the retarget is the interesting part

This guard scanned `src/application/` — one tree, with `use_cases/` and `ports/`
subdirectories — and that tree is **now empty**. PR 3.1c moved the last thing in
it (`use_cases/backtest`) into `modules/backtesting/`, and PR 2.1c-2 had already
taken `event_handlers/`; `ports/` went with `trading` in PR 1.3a. A
path-scanning guard whose subject has left does not fail, it passes faster —
which is the failure `ui_trees.py` was written after paying for three times, and
`test_scanned_roots_are_not_empty.py` is what caught it here.

So the subject moves to `src/modules/*/application/`, where the same two rules
apply — **measured before retargeting, not assumed**: across 105 files in four
modules' `application/` trees there are zero misnamed CQRS files and zero `I*`
classes. The rules transfer; only the address changed.

What changed with the address is the second rule's *other half*. In the legacy
tree the question was "is this interface under `application/ports/`"; in a
module there is no `ports/` at all, because a module's abstractions are its
`contracts/` — the one importable surface (HLD §3.2). The rule is therefore
stricter now and easier to state: **no `I*` class under `application/`, full
stop.**

Pure static analysis (`ast`) — no PySide6, no database, no `qapp` fixture.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MODULES_ROOT = _REPO_ROOT / "src" / "modules"

#: An interface name: `I` followed by an upper-case letter, so `IOrderSubmission`
#: matches and `Indicator` does not.
_INTERFACE_NAME = re.compile(r"^I[A-Z]")


def _application_files() -> list[Path]:
    """Every `.py` under any module's `application/` tree."""
    return sorted(
        p
        for p in _MODULES_ROOT.rglob("application/**/*.py")
        if "__pycache__" not in p.parts
    )


def _class_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def _cqrs_expected_filename(class_name: str) -> str | None:
    """The file a CQRS class belongs in, or `None` if it is not one.

    Interface names are excluded: `ICommandHandler`/`IQueryHandler` are the
    abstract protocols in `core/contracts/`, not concrete use-case classes, and
    an interface's placement is the other test's subject.
    """
    if _INTERFACE_NAME.match(class_name):
        return None
    if class_name.endswith(("CommandHandler", "QueryHandler")):
        return "handler.py"
    if class_name.endswith("Command"):
        return "command.py"
    if class_name.endswith("Query"):
        return "query.py"
    return None


def test_the_guard_has_a_subject() -> None:
    """Locked at "more than fifty" rather than an exact number, because the
    count moves with every use case this epic brings in. The point is that an
    empty scan must fail loudly rather than pass fast — this guard spent PR
    3.1c's predecessor scanning a tree that had emptied out underneath it."""
    files = _application_files()

    assert len(files) > 50, (
        f"only {len(files)} file(s) under src/modules/*/application/. Either "
        "the modules' application trees moved again, or this guard is now "
        "reading nothing and would pass on anything."
    )


def test_cqrs_files_match_command_query_handler_naming() -> None:
    offenders = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}: {name} (expected {expected})"
        for path in _application_files()
        for name in _class_names(path)
        if (expected := _cqrs_expected_filename(name)) is not None
        and path.name != expected
    ]

    assert offenders == [], (
        "a Command/Query/Handler class must live in the file named for its "
        "role, one role per file (ADR D2):\n  " + "\n  ".join(offenders)
    )


def test_no_interface_class_lives_under_a_modules_application_tree() -> None:
    """A module's abstractions are its `contracts/` — the one surface another
    context may import (HLD §3.2). An `I*` class under `application/` is a port
    that no consumer can reach without crossing the boundary guard, which is
    how `trading`'s five `application/ports/` files came to be five allowlist
    entries before PR 1.3a moved them."""
    offenders = [
        f"{path.relative_to(_REPO_ROOT).as_posix()}: {name}"
        for path in _application_files()
        for name in _class_names(path)
        if _INTERFACE_NAME.match(name)
    ]

    assert offenders == [], (
        "these interface classes are under a module's `application/` tree; a "
        "module's abstractions belong in its `contracts/`:\n  " + "\n  ".join(offenders)
    )
