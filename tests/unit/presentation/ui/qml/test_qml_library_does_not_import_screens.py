"""`EPIC-021L`/`BUG-082` — the shared `qml/` widget library must never
import `presentation.ui.screens`: that is the one direction
`stat_card_row_widget.py` documents this rollout uses throughout, and a
widget that depends on a specific screen can no longer be reused by
another one (exactly what blocked `EPIC-021I`'s Trading screen from
reusing `qml/TradeLogTable/`).

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

_REPO_ROOT = Path(__file__).resolve().parents[5]
_QML_DIR = _REPO_ROOT / "src" / "presentation" / "ui" / "qml"
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


def _files_importing_screens() -> list[Path]:
    hits: list[Path] = []
    for path in sorted(_QML_DIR.rglob("*.py")):
        if _imports_screens(path.read_text(encoding="utf-8"), str(path)):
            hits.append(path)
    return hits


def test_qml_library_never_imports_screens() -> None:
    hits = _files_importing_screens()
    assert hits == [], (
        "src/presentation/ui/qml/ must never import presentation.ui.screens "
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
