"""
@brief `Surface` — the abstract gate of the Surface/Card/Panel family. See
`widgets.style` for why this family shares no base with `Overlay` or the
`Styled*` controls despite all reading as "token-styled" — PySide6/Shiboken
forbids inheriting two QObject-derived bases, so each family's shared
behaviour lives here, per-family, not in one widget-wide mixin.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .style import StyleRole, WidgetState, apply_role


class Surface(QFrame):
    """
    @brief A token-styled, enabled-state-aware background region that other
    widgets are placed inside. The abstract gate of this family — always
    instantiate `Card` or `Panel`, never `Surface` itself.

    @details `@abstractmethod`/`ABCMeta` cannot enforce this reliably for a
    QWidget subclass: verified empirically that PySide6/Shiboken's metaclass
    does not cooperate with `ABCMeta`'s instantiation check (a
    `Surface(QFrame, metaclass=_QtABCMeta)` with an `@abstractmethod`
    constructs without error despite never implementing it). The
    `type(self) is Surface` guard below is the reliable alternative for a
    Qt widget base — a plain Python `TypeError` at construction time, not
    relying on any `abc` machinery Shiboken doesn't honour.

    `setEnabled()` is not overridden: Qt's own cascade already disables
    every child widget, which is the entire behaviour the QML kit's
    `BaseCard.setDisabled()` had to hand-roll (see EPIC-006's architecture
    ADR §4 — this is why `FormCard`/`TableCard`/`ActionCard` never needed a
    QtWidgets equivalent). `_on_enabled_changed()` exists only for a
    subclass that needs something Qt's cascade does not already give it for
    free (see `changeEvent` below).
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        if type(self) is Surface:
            raise TypeError("Surface is abstract — instantiate Card or Panel instead.")
        super().__init__(parent)
        self.body_layout = QVBoxLayout(self)
        apply_role(self, StyleRole.SURFACE)

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange:
            self._on_enabled_changed(self.isEnabled())

    def _on_enabled_changed(self, enabled: bool) -> None:
        """Hook for a subclass needing behaviour beyond Qt's own
        `setEnabled()` cascade (e.g. pausing a live feed — see `LogPanel`).
        No-op by default."""


class Panel(Surface):
    """A bare `Surface` with no header — the plain grouping-box shape.
    Concrete; construct directly for a titleless region, or subclass for
    reusable custom content."""


class Card(Surface):
    """
    @brief A `Surface` with a header row: `title` + a `header_actions` slot
    for header-level controls (e.g. `LogPanel`'s Copy/Clear buttons).

    @details Concrete, unlike `Surface` — a `Card("Sync Controls")` is a
    complete, useful widget on its own; subclass only when real behaviour
    (not just content) differs, matching `ui-architecture.md`'s tier-1/
    tier-2 split (structure here, content is the consumer's).
    `body_layout` (inherited from `Surface`) is where a subclass or
    consumer adds its own content, below the header this class inserts.
    """

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        header = QWidget()
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 0)
        self._title_label = QLabel(title)
        header_row.addWidget(self._title_label)
        header_row.addStretch()
        self.header_actions = QHBoxLayout()
        header_row.addLayout(self.header_actions)
        self.body_layout.addWidget(header)

    @property
    def title(self) -> str:
        return self._title_label.text()

    @title.setter
    def title(self, value: str) -> None:
        self._title_label.setText(value)


class SelectableCard(Panel):
    """
    @brief A bare `Panel` that is also clickable and can be the user's
    current choice among siblings — one row of a picker list (a strategy,
    a timeframe, a timezone, ...).

    @details Not a `QAbstractButton` subclass — `Panel`/`Surface`'s own
    `QFrame` lineage already carries the token styling this needs, and a
    second Qt base is forbidden (see `widgets.style`'s module docstring).
    `clicked` is emitted from `mouseReleaseEvent` only when the matching
    `mousePressEvent` also landed inside this widget's bounds (the same
    press-then-release-inside contract `QAbstractButton` itself uses),
    so a drag that starts here and releases elsewhere does not fire it.
    """

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._selected = False
        self._pressed_inside = False
        apply_role(self, StyleRole.SELECTABLE_CARD)

    @property
    def selected(self) -> bool:
        return self._selected

    @selected.setter
    def selected(self, value: bool) -> None:
        self._selected = bool(value)
        apply_role(
            self,
            StyleRole.SELECTABLE_CARD,
            state=WidgetState.SELECTED if self._selected else WidgetState.NORMAL,
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed_inside = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        was_pressed_inside = self._pressed_inside
        self._pressed_inside = False
        if (
            was_pressed_inside
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)
