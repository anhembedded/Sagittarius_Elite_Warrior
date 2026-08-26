"""
The coverage guard EPIC-007C required — the QtWidgets counterpart to
`kit.gallery_coverage_guard`, and the gap `kit/guards.py`'s own module
docstring records as outstanding:

    "No coverage-guard counterpart yet (`kit.gallery_coverage_guard`'s
    QtWidgets equivalent) — that guard checks every kit type appears in a
    showcase, and no QtWidgets showcase/preview exists yet to check
    against."

There is one now.
"""

from __future__ import annotations

import inspect

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui import kit as widgets
from Sagittarius_Elite_Warrior.tools.kit_showcase import showcased_types

#: Exports that are not widgets and so cannot appear in a gallery: value
#: types, enums, protocols, the guard functions, and the two abstract gates
#: a subclass is always instantiated in place of.
#:
#: Listed by name rather than filtered by `issubclass(QWidget)` alone,
#: because that test would also silently excuse a real widget someone
#: forgot — the point of this guard is that skipping something has to be a
#: decision written down here.
_NOT_SHOWCASEABLE = frozenset(
    {
        # Value types and enums.
        "Column",
        "PickerItem",
        "RowAction",
        "Pagination",
        "Severity",
        "StyleRole",
        "Tab",
        "Tone",
        "WidgetState",
        # A structural protocol, not a class to construct.
        "LogModel",
        # Abstract gates — instantiating either raises TypeError by design.
        "Overlay",
        "Surface",
        "StyledLabel",
        # Findings and functions.
        "BareQtBaseFinding",
        "InlineStylesheetFinding",
        "apply_role",
        "semantic_colour",
        "tone_colour",
        "find_bare_qt_base_widgets",
        "find_inline_stylesheets",
        "format_bare_qt_base_findings",
        "format_inline_stylesheet_findings",
    }
)


def _widget_exports() -> set[str]:
    names = set()
    for name in widgets.__all__:
        exported = getattr(widgets, name)
        if inspect.isclass(exported) and issubclass(exported, QWidget):
            names.add(name)
    return names


def test_every_exported_widget_appears_in_the_showcase(qtbot):
    expected = _widget_exports() - _NOT_SHOWCASEABLE
    shown = showcased_types()

    missing = sorted(expected - shown)

    assert missing == [], (
        "these widget types are exported but never built by the showcase — "
        "add them to tools/kit_showcase, or record why they cannot be "
        f"shown in _NOT_SHOWCASEABLE: {missing}"
    )


def test_the_skip_list_names_only_real_exports(qtbot):
    """A skip list that outlives what it skipped stops being a record of
    decisions and becomes a place things hide."""
    stale = sorted(_NOT_SHOWCASEABLE - set(widgets.__all__))

    assert stale == [], f"_NOT_SHOWCASEABLE names things no longer exported: {stale}"


def test_the_guard_fails_when_a_type_is_dropped(qtbot):
    """EPIC-007C asks for the guard to be demonstrated failing, not merely
    to pass. Removing one type from what the showcase reports must make the
    comparison above fail — otherwise the guard is green for the wrong
    reason and nobody would know."""
    expected = _widget_exports() - _NOT_SHOWCASEABLE
    shown = showcased_types()
    assert expected - shown == set(), "precondition: the guard is currently green"

    victim = min(expected)
    weakened = shown - {victim}

    assert sorted(expected - weakened) == [victim]
