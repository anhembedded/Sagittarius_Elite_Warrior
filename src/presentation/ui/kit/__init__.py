"""
@brief The UI Engine's QtWidgets widget base classes — the replacement for
`Sagittarius/UI/`'s QML kit (EPIC-006, `Sagittarius_Elite_Warrior`'s
project-wide move off QML). See
`Sagittarius_Elite_Warrior/Tasks/epics/EPIC-006_drop_qml/
DECISION_2026-08-24_widget_architecture.md` for the full architecture
rationale.

@details
Same ownership boundary as the QML kit before it (`ui-architecture.md` §1):
this package knows no consuming application, screen, or domain concept —
only shapes (`Surface`/`Card`/`Panel`, `Overlay`, `Styled*` controls). A
consuming app names things (`ChartCard`, `GapInspectorOverlay`) by
subclassing from here; it never authors a bare `QFrame`/`QDialog`, and
never builds a stylesheet string outside its own call to `apply_role()`
(see `style.py`, `guards.py`).

Four independent single-inheritance chains, deliberately not one shared
base — PySide6/Shiboken forbids a class inheriting two QObject-derived
bases, which rules out a mixin shared across `QFrame`/`QDialog`/
`QPushButton`/`QCheckBox`/`QLineEdit`/`QDateTimeEdit` lineages. Shared
styling behaviour lives in `apply_role()` (composition), not inheritance.
"""

from __future__ import annotations

from .controls import (
    Badge,
    DateTimeField,
    SectionLabel,
    StyledButton,
    StyledCheckBox,
    StyledField,
    StyledLabel,
    StyledProgressBar,
)
from .guards import (
    BareQtBaseFinding,
    InlineStylesheetFinding,
    find_bare_qt_base_widgets,
    find_inline_stylesheets,
    find_unscoped_container_stylesheets,
    format_bare_qt_base_findings,
    format_inline_stylesheet_findings,
    format_unscoped_container_findings,
)
from .overlay import Overlay
from .overlays import (
    ConfirmOverlay,
    DateRangeOverlay,
    PickerItem,
    PickerOverlay,
    RangePreset,
)
from .style import (
    StyleRole,
    Tone,
    WidgetState,
    apply_role,
    semantic_colour,
    tone_colour,
)
from .surface import Card, Panel, SelectableCard, Surface
from .surfaces import (
    Banner,
    Column,
    DataRow,
    LogModel,
    LogPanel,
    Pagination,
    RowAction,
    Severity,
    StatCard,
    Tab,
    TabBar,
    TableCard,
)

__all__ = [
    "Badge",
    "Banner",
    "BareQtBaseFinding",
    "Card",
    "Column",
    "ConfirmOverlay",
    "DataRow",
    "DateRangeOverlay",
    "DateTimeField",
    "InlineStylesheetFinding",
    "LogModel",
    "LogPanel",
    "Overlay",
    "Pagination",
    "Panel",
    "PickerItem",
    "PickerOverlay",
    "RangePreset",
    "RowAction",
    "SectionLabel",
    "SelectableCard",
    "Severity",
    "StatCard",
    "StyleRole",
    "StyledButton",
    "StyledCheckBox",
    "StyledField",
    "StyledLabel",
    "StyledProgressBar",
    "Surface",
    "Tab",
    "TabBar",
    "TableCard",
    "Tone",
    "WidgetState",
    "apply_role",
    "find_bare_qt_base_widgets",
    "find_inline_stylesheets",
    "find_unscoped_container_stylesheets",
    "format_bare_qt_base_findings",
    "format_inline_stylesheet_findings",
    "format_unscoped_container_findings",
    "semantic_colour",
    "tone_colour",
]
