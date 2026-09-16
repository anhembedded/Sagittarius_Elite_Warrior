"""
@brief `ChecklistOverlay` — an `Overlay` of independently checkable rows, some
of them locked, where toggling never closes the dialog.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCheckBox, QLabel, QScrollArea, QVBoxLayout, QWidget

from ..overlay import Overlay


@dataclass(frozen=True)
class ChecklistItem:
    """
    @brief One row: the `key` a consumer gets back on a toggle, the `label` a
    user reads, whether it starts `checked`, whether it is `locked`, and an
    optional `tooltip` explaining a cost.

    @details `locked` **disables** the row rather than hiding it — a locked row
    still says what it is, which is the behaviour the two consuming dialogs
    have had since before either toolkit.
    """

    key: str
    label: str
    checked: bool = False
    locked: bool = False
    tooltip: str = ""


class ChecklistOverlay(Overlay):
    """
    @brief Rows a user ticks independently, reported one toggle at a time.

    @details
    **Why this is not `PickerOverlay` with a flag.** That class's docstring
    named this shape as a candidate and declined to guess at it: *"multi-select,
    toggles checkboxes, and never closes — a genuinely different interaction,
    not a parameter of this one"*. `EPIC-025` PR 4.3f is the step that needed
    it, and the judgement held — a picker emits *the* choice and its consumers
    accept on it; a checklist emits *a* change and its consumers stay open.

    **It renders state and reports toggles; it decides nothing.** `toggled`
    carries `(key, checked)` raw, and a consumer that has a cross-row rule
    (the app's order-execution dialog: two of its four rows are mutually
    exclusive) enforces it by writing its own state and calling `set_items()`
    again. A rule living in a widget is a rule its consumers cannot see.

    `set_items()` is the only way rows change, and it is safe to call from
    `showEvent` on every open — the shape every dialog in this app needs,
    because its rows arrive from a live model. See its own docstring for why an
    unchanged key set is updated in place rather than rebuilt.
    """

    #: (key, checked). Not a set of checked keys: a consumer wants to know
    #: *what changed*, and the two in this app both act on a single row.
    toggled = Signal(str, bool)

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        *,
        empty_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, subtitle, parent=parent)

        self._items: list[ChecklistItem] = []
        self._boxes: dict[str, QCheckBox] = {}

        self._empty_label = QLabel(empty_text)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setVisible(False)
        self.body_layout.addWidget(self._empty_label)

        self._rows_host = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._rows_host)
        self.body_layout.addWidget(self._scroll, 1)

    @property
    def items(self) -> tuple[ChecklistItem, ...]:
        """What is currently offered, in order."""
        return tuple(self._items)

    def checkbox_for(self, key: str) -> QCheckBox | None:
        """The row's own control, or `None` for a key not offered.

        Public because a consumer's tests need to click a row, and reaching
        through a private layout to find one is how a test starts depending on
        this class's internals.
        """
        return self._boxes.get(key)

    def set_items(self, items: Sequence[ChecklistItem]) -> None:
        """@brief Replaces the rows and re-renders.

        Rows whose **keys and order** are unchanged are updated in place
        rather than rebuilt, and that is a correctness requirement rather than
        an optimisation: a consumer with a cross-row rule reaches this method
        *from inside* a `toggled` emission (toggle a row → write the screen's
        state → its change signal → `set_items` again), and rebuilding there
        would tear down the checkbox whose signal is still being delivered.
        It also keeps keyboard focus on the row the user just ticked.
        """
        wanted = list(items)
        same_keys = [item.key for item in wanted] == [item.key for item in self._items]
        self._items = wanted
        if same_keys:
            self._update_in_place()
        else:
            self._rebuild()
        # Outside both paths, because "no rows" reaches the in-place one:
        # empty to empty is an unchanged key set, and the first `set_items([])`
        # of a freshly built overlay has to raise its empty label all the same.
        self._render_empty_state()

    def _render_empty_state(self) -> None:
        self._empty_label.setVisible(not self._items)
        self._scroll.setVisible(bool(self._items))

    def _update_in_place(self) -> None:
        for item in self._items:
            box = self._boxes[item.key]
            # Blocked, so writing the state a consumer just asked for does not
            # come back as a second user toggle.
            was_blocked = box.blockSignals(True)
            try:
                box.setChecked(item.checked)
            finally:
                box.blockSignals(was_blocked)
            box.setEnabled(not item.locked)
            box.setToolTip(item.tooltip)
            box.setText(item.label)

    def _rebuild(self) -> None:
        while self._rows_layout.count():
            entry = self._rows_layout.takeAt(0)
            if entry is None:  # pragma: no cover — count() > 0 guarantees one
                break
            widget = entry.widget()
            if widget is not None:
                # Detached before the deferred delete, which the main event
                # loop delivers rather than this call: without it the host
                # still holds the previous rows in between.
                widget.setParent(None)
                widget.deleteLater()
        self._boxes.clear()

        for item in self._items:
            box = QCheckBox(item.label)
            box.setObjectName(f"chk_{item.key}")
            # Checked before connecting, so seeding the row does not arrive at
            # the consumer as a user's toggle. The alternative — a `_syncing`
            # flag — is a second state to keep right.
            box.setChecked(item.checked)
            box.setEnabled(not item.locked)
            if item.tooltip:
                box.setToolTip(item.tooltip)
            box.toggled.connect(
                # Default-arg capture, not a closure over `item`: a plain
                # closure would hand every row the last key of the loop.
                lambda checked, key=item.key: self.toggled.emit(key, checked)
            )
            self._rows_layout.addWidget(box)
            self._boxes[item.key] = box
