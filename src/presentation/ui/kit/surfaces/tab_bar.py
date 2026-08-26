"""
@brief `TabBar` — a row of selectable tabs, each with an optional badge.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from ..controls import Badge
from ..style import StyleRole, WidgetState, apply_role


@dataclass(frozen=True)
class Tab:
    """
    @brief One tab: the id a caller identifies it by, the text a user reads,
    and an optional badge.

    @details `badge` is a pre-formatted string, not a count — the reference
    consumer's real badges read "12 LỆNH" and "340 EVENTS", so a numeric
    field would force every caller to hand back a string anyway, minus the
    ability to render an empty one as absent.
    """

    id: str
    label: str
    badge: str = ""


class _TabButton(QPushButton):  # base-exempt: a tab is a button, not a surface
    """One tab. Not public — a caller describes tabs with `Tab` and lets the
    bar build them, which is what keeps the bar's selection state and its
    buttons from disagreeing."""

    def __init__(self, tab: Tab, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        row = QHBoxLayout(self)
        self._label = QLabel(tab.label)
        row.addWidget(self._label)

        self._badge = Badge(tab.badge)
        row.addWidget(self._badge)

        self.set_active(False)

    def set_badge(self, badge: str) -> None:
        self._badge.setText(badge)

    def set_label(self, label: str) -> None:
        self._label.setText(label)

    def set_active(self, active: bool) -> None:
        apply_role(
            self,
            StyleRole.SECONDARY_BUTTON,
            state=WidgetState.NORMAL if active else WidgetState.DISABLED,
        )
        self._badge.set_emphasised(active)

    # `QPushButton` sizes itself from its own text and icon. This one has
    # neither — its content is the label and badge in the layout below it,
    # which the base class does not look at. Without these two overrides the
    # button asks for 59x24 while its content needs 195x34, and every tab
    # renders with its label clipped to the first two characters (`BUG-012`).
    def sizeHint(self) -> QSize:
        return self.layout().sizeHint()

    def minimumSizeHint(self) -> QSize:
        return self.layout().minimumSize()


class TabBar(QWidget):  # base-exempt: a row of tabs is chrome, not a surface
    """
    @brief A row of tabs where exactly one is current.

    @details
    Built from the reference consumer's two tab rows: its dynamic bottom bar
    (dict-described tabs with count badges, selection held on the bar) and
    its trade-log filter row (a fixed tuple of `(value, label)` pairs, no
    badges, selection held in the view model and pushed back down).

    Those two disagree on where selection lives, and this class picks the
    first: the bar owns `current_id`. The filter row's model — every button
    stateless, a click writing straight to a view model whose change signal
    repaints the row — is not lost by that choice: such a consumer simply
    ignores `current_id` and calls `set_current_id()` from its own sync, and
    the bar's copy follows rather than leads. The reverse does not work; a
    stateless bar cannot serve a consumer that has no view model to hold the
    selection for it.

    **`set_current_id()` does not emit.** Only a user's click does. A
    programmatic set that emitted would loop straight back through the
    consumer's own sync handler, and the filter row above is exactly the
    shape that would loop.

    **`set_tabs()` updates in place where it can.** The consumer's bar
    destroys and recreates every button on every call, and its own panel
    calls it on every single log line that arrives — so a live backtest
    rebuilds that row hundreds of times to change one number. When the ids
    are unchanged, this only writes the labels and badges.

    **Not a `Surface`.** It was a `Panel` at first, which gave every tab row
    a card background, a border and a radius of its own. That is wrong for
    the same reason `_TabButton` above already carries `base-exempt`: a tab
    is a button, not a surface — and a row of buttons is not one either. A
    tab bar is chrome that sits *on* a surface. An app wanting it framed
    puts it inside a `Panel`; an app that does not, as the reference
    consumer does not, cannot un-frame a `Panel`.
    """

    #: Emits `(index, id)` on a user's click. Both, because the consumer's
    #: two rows identify a tab differently — one by position, one by id —
    #: and neither should have to look the other up.
    tab_selected = Signal(int, str)

    def __init__(
        self,
        tabs: Sequence[Tab] = (),
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tabs: tuple[Tab, ...] = ()
        self._buttons: list[_TabButton] = []
        self._current_id: str | None = None

        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(0, 0, 0, 0)

        self.set_tabs(tabs)

    @property
    def tabs(self) -> tuple[Tab, ...]:
        return self._tabs

    @property
    def current_id(self) -> str | None:
        return self._current_id

    @property
    def current_index(self) -> int:
        """Position of the current tab, or `-1` when nothing is current."""
        for index, tab in enumerate(self._tabs):
            if tab.id == self._current_id:
                return index
        return -1

    def set_tabs(self, tabs: Sequence[Tab]) -> None:
        """@brief Replaces the tabs. Rebuilds only when the ids changed;
        otherwise refreshes labels and badges in place."""
        new_tabs = tuple(tabs)
        ids_unchanged = [t.id for t in new_tabs] == [t.id for t in self._tabs]
        self._tabs = new_tabs

        if ids_unchanged:
            for button, tab in zip(self._buttons, new_tabs, strict=True):
                button.set_label(tab.label)
                button.set_badge(tab.badge)
            return

        self._rebuild()

    def set_current_id(self, tab_id: str | None) -> None:
        """@brief Marks a tab current without emitting `tab_selected`."""
        if tab_id == self._current_id:
            return
        self._current_id = tab_id
        self._apply_active()

    def _rebuild(self) -> None:
        while self._row.count():
            entry = self._row.takeAt(0)
            if entry is None:  # pragma: no cover — count() > 0 guarantees one
                break
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()
        self._buttons = []

        for index, tab in enumerate(self._tabs):
            button = _TabButton(tab)
            button.clicked.connect(lambda _checked=False, i=index: self._on_clicked(i))
            self._row.addWidget(button)
            self._buttons.append(button)
        self._row.addStretch(1)

        if self._current_id is None and self._tabs:
            self._current_id = self._tabs[0].id
        elif self._current_id not in {tab.id for tab in self._tabs}:
            self._current_id = self._tabs[0].id if self._tabs else None
        self._apply_active()

    def _apply_active(self) -> None:
        for button, tab in zip(self._buttons, self._tabs, strict=True):
            button.set_active(tab.id == self._current_id)

    def _on_clicked(self, index: int) -> None:
        tab = self._tabs[index]
        self._current_id = tab.id
        self._apply_active()
        self.tab_selected.emit(index, tab.id)
