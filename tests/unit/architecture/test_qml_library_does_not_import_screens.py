"""`EPIC-021L`/`BUG-082` — a **shared widget library** must never import
`presentation.ui.screens`: a widget that depends on one screen can no longer
be reused by another, which is exactly what blocked `EPIC-021I`'s Trading
screen from reusing `qml/TradeLogTable/`.

@par The rule outlived its address, twice
It was written for `src/presentation/ui/qml/`, and `EPIC-025` PR 4.3l deleted
that tree entirely (ADR D21: `.qml` is at zero). A path-scanning guard whose
subject has vanished **passes faster rather than failing** — PR 3.1c's lesson,
and the reason this file was retargeted instead of deleted with the directory.
The shared libraries are `support/ui_kit/` and `support/charting/` now, so
that is what it scans; both measured clean at the retarget.

@details Scans by `ast` for an `ImportFrom`/`Import` node whose module path
mentions `presentation.ui.screens` (absolute or dotted-relative-resolved),
not plain text — a docstring or comment *explaining* this rule (like this
one) necessarily has to spell out the package name it restricts, and
flagging that would make the rule impossible to document. Mirrors
`test_order_submission_mode_live_is_restricted.py`'s shape (`EPIC-021F`).
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
#: Every shared widget library in `src/`. A package added beside these two
#: needs a row here, or this guard scans a smaller tree than the libraries
#: occupy — the failure `ui_trees.py` exists to prevent, four occurrences in.
_LIBRARY_DIRS = (
    _REPO_ROOT / "src" / "support" / "ui_kit",
    _REPO_ROOT / "src" / "support" / "charting",
)
_FORBIDDEN_SUBSTRING = "presentation.ui.screens"


def _imports_screens(source: str, filename: str) -> bool:
    tree = ast.parse(source, filename=filename)
    for node in ast.walk(tree):
        if (
            (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and _FORBIDDEN_SUBSTRING in node.module
            )
            or isinstance(node, ast.Import)
            and any(_FORBIDDEN_SUBSTRING in alias.name for alias in node.names)
        ):
            return True
    return False


def _library_files() -> list[Path]:
    return sorted(
        path
        for directory in _LIBRARY_DIRS
        for path in directory.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def _files_importing_screens() -> list[Path]:
    return [
        path
        for path in _library_files()
        if _imports_screens(path.read_text(encoding="utf-8"), str(path))
    ]


def test_the_guard_has_a_subject() -> None:
    """A path-scanning guard that has lost its tree passes faster rather than
    failing (PR 3.1c). This one has been retargeted once already."""
    files = _library_files()
    assert len(files) > 50, f"the shared libraries scan too small a tree: {len(files)}"


def test_qml_library_never_imports_screens() -> None:
    hits = _files_importing_screens()
    assert hits == [], (
        "a shared widget library must never import presentation.ui.screens "
        f"(BUG-082): {[str(p.relative_to(_REPO_ROOT)) for p in hits]}"
    )


def test_guard_actually_detects_a_violation() -> None:
    """Mutation-verify (`testing-rule.md` §2): prove the scanner fires on a
    real usage shape, and correctly ignores a docstring merely naming it."""
    assert _imports_screens(
        "from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic"
        ".trade_log_row import TradeLogRow\n",
        "<violation-fixture>",
    )
    assert not _imports_screens(
        '"""Must never import presentation.ui.screens here."""\n',
        "<docstring-only-fixture>",
    )
