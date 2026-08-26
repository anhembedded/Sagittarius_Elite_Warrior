"""Package-level guarantees for `widgets.surfaces` — EPIC-007B §1, §3, §5."""

from __future__ import annotations

from pathlib import Path

from Sagittarius_Elite_Warrior.src.presentation.ui import kit as widgets
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import surfaces
from Sagittarius_Elite_Warrior.src.presentation.ui.kit.guards import (
    find_bare_qt_base_widgets,
    find_inline_stylesheets,
    format_bare_qt_base_findings,
    format_inline_stylesheet_findings,
)

_PACKAGE_ROOT = Path(surfaces.__file__).parent

#: The six shapes EPIC-007B extracted, plus the value types they are
#: described with. Listed literally rather than derived from `__all__`, so
#: this fails if something is dropped from the package as well as if the
#: re-export is forgotten.
#:
#: `Tone` was here until EPIC-007C and now lives in `widgets.style`: once
#: `Badge` needed it too, "how does this figure read" stopped being a stat
#: card's idea and became a styling one.
_EXPECTED_EXPORTS = (
    "Banner",
    "Column",
    "DataRow",
    "LogModel",
    "LogPanel",
    "Pagination",
    "RowAction",
    "Severity",
    "StatCard",
    "Tab",
    "TabBar",
    "TableCard",
)


def test_no_literal_colours_in_the_surfaces_package():
    """§5. `style.py` is the one file allowed a colour literal, and none of
    these six may reintroduce one — the 130 hex literals this epic exists
    to remove all began as one widget being 'just slightly' off-token."""
    findings = find_inline_stylesheets(_PACKAGE_ROOT)

    assert findings == [], format_inline_stylesheet_findings(findings)


def test_no_bare_qt_bases_in_the_surfaces_package():
    """The guard EPIC-007A widened, pointed at the code written right after
    it. Everything that is a surface derives `Card` or `Panel`; the three
    things that are not carry a reasoned `base-exempt` marker — `_TabButton`
    (a tab is a button), `TabBar` (a row of those buttons is chrome), and
    `DataRow` (a row inside a table is content sitting on the table).

    The last two were `Panel` subclasses until `EPIC-007F` put a real
    consumer in front of them and both drew a card frame nothing wanted.
    Passing this guard has never meant "everything inherits a surface"; it
    means every non-surface says why."""
    findings = find_bare_qt_base_widgets(_PACKAGE_ROOT)

    assert findings == [], format_bare_qt_base_findings(findings)


def test_one_class_per_file():
    """§1. `surface.py` keeps the four roots; every shape added by this epic
    gets its own module."""
    modules = sorted(
        path.stem for path in _PACKAGE_ROOT.glob("*.py") if path.stem != "__init__"
    )

    assert modules == [
        "banner",
        "data_row",
        "log_panel",
        "stat_card",
        "tab_bar",
        "table_card",
    ]


def test_every_shape_is_re_exported_from_widgets():
    """A consumer imports from `widgets`, not from `widgets.surfaces.banner`
    — the package layout is this package's business, not its callers'."""
    for name in _EXPECTED_EXPORTS:
        assert name in surfaces.__all__, f"{name} missing from surfaces.__all__"
        assert name in widgets.__all__, f"{name} missing from widgets.__all__"
        assert getattr(widgets, name) is getattr(surfaces, name)


def test_no_consuming_application_vocabulary_leaks_in():
    """§3. This package must not know that trading, candles or backtests
    exist. Docstrings cite the reference consumer's widgets by name, which
    is how the extraction stays reviewable — so this checks the code, not
    the prose."""
    import ast

    forbidden = ("trade", "kline", "candle", "symbol", "backtest", "binance")
    offenders: list[str] = []

    for path in _PACKAGE_ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.ClassDef | ast.FunctionDef):
                name = node.name
            elif isinstance(node, ast.Name):
                name = node.id
            elif isinstance(node, ast.arg):
                name = node.arg
            if name and any(word in name.lower() for word in forbidden):
                offenders.append(f"{path.name}:{node.lineno}: {name}")

    assert offenders == [], "domain vocabulary in engine code: " + "; ".join(offenders)
