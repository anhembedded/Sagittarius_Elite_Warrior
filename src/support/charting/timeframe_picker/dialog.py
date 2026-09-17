"""The full timeframe picker: every interval the domain has, in its groups.

`EPIC-025` PR 4.3k: was `TimeframePicker.qml` + `TimeframePickerCard.qml`, a
grid of hand-drawn cells each with a `★`/`☆` glyph and a `MouseArea` per half.
It is a `QTreeWidget` now — headings with rows under them, which is what the
groups always were, and a real check box for the pin, which is what a pin always
was.

## Choose-and-close, and no footer buttons of its own

Picking an interval closes the dialog, as it has in every version of this
widget: there is no separate Apply step, and Escape or the window's close
control is how a caller backs out without choosing. So `Overlay`'s default empty
footer is exactly right and this class does not override `_build_buttons()`.

Pinning is the one interaction that does **not** close: a user pinning three
intervals to their chart header is doing something other than choosing one, and
closing on the first star would make that impossible.

## Two ways in, the same as before

`TimeframePickerDialog(selection)` shares an existing `TimeframeSelection` —
`ChartToolbar` is the caller that must, because its pill row reads the same
pinned set. `from_callbacks()` builds a private one for every other caller
(Settings, Data Management, Backtest's modal-only picker), where this dialog is
the only consumer of timeframe state and there is nothing to share with.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Overlay

from .selection import TimeframeSelection

_DEFAULT_TITLE = "SELECT TIMEFRAME"
_INTERVAL_COLUMN = 0
_DESCRIPTION_COLUMN = 1
_PIN_COLUMN = 2
_COLUMNS = ("Interval", "", "Pinned")
_CODE_ROLE = Qt.ItemDataRole.UserRole

_WARNING_TEXT = (
    "Timeframes under 1 minute generate a lot of candles — one day of 1s data"
    " is ~86,400 candles."
)
_PIN_HINT = "Tick a row to keep that interval on the chart toolbar."


class PinnedTimeframes:
    """Session-only pinned set, for a caller with nowhere to persist one.

    @details A screen's composition root constructs one instance (never shared
    across screens) and passes `get`/`set` straight through as
    `TimeframeSelection`'s `get_pinned`/`set_pinned`. In memory and not
    persisted: pinning visibly toggles a row for the rest of the session and
    resets on the next launch.

    `ChartToolbar` persists instead, per chart symbol, through
    `TimeframePinPreferences` — see that module. This class remains the real
    state for every `from_callbacks()` caller (Settings, Data Management,
    Backtest's modal-only picker: none of them drives a persistent chart, so
    nothing asked for their pins to survive a restart) and is `ChartToolbar`'s
    own fallback when it is constructed with no symbol to scope to.

    @param initial Codes pinned from construction — empty by default, since a
        picker with no toolbar has no need for a non-empty starting set.
    """

    def __init__(self, initial: Iterable[str] = ()) -> None:
        self._codes: set[str] = set(initial)

    def get(self) -> list[str]:
        return sorted(self._codes)

    def set(self, code: str, pinned: bool) -> None:
        if pinned:
            self._codes.add(code)
        else:
            self._codes.discard(code)


class TimeframePickerDialog(Overlay):
    """
    @brief Choose a candle interval, and pin the ones worth keeping to hand.

    @param selection The state this dialog reads and writes. Construct it
        yourself, and keep the reference, when something else must share it.
    """

    #: The chosen code. Re-emitted from the selection rather than emitted
    #: directly, so a caller sharing a `TimeframeSelection` can listen to
    #: either one and hear a choice exactly once.
    chosen = Signal(str)

    def __init__(
        self,
        selection: TimeframeSelection,
        *,
        title: str = _DEFAULT_TITLE,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, _PIN_HINT, parent=parent)
        self.setObjectName("timeframePickerDialog")
        self.resize(560, 520)
        self._selection = selection
        #: Set while this widget writes check states itself, so the
        #: `itemChanged` those writes raise is not read back as a user ticking
        #: a pin.
        self._filling = False
        #: The structure currently on screen — see `_render`.
        self._rendered_signature: tuple[tuple[str, tuple[str, ...]], ...] = ()

        self._tree = QTreeWidget()
        self._tree.setObjectName("timeframePickerBody")
        self._tree.setColumnCount(len(_COLUMNS))
        self._tree.setHeaderLabels(list(_COLUMNS))
        self._tree.setRootIsDecorated(False)
        # Groups are headings, not folders — a collapsed group would hide
        # intervals the user opened this to pick from.
        self._tree.setItemsExpandable(False)
        self._tree.setUniformRowHeights(True)
        header = self._tree.header()
        header.setSectionResizeMode(_INTERVAL_COLUMN, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(_DESCRIPTION_COLUMN, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            _PIN_COLUMN, QHeaderView.ResizeMode.ResizeToContents
        )
        self._tree.itemActivated.connect(self._on_activated)
        self._tree.itemClicked.connect(self._on_clicked)
        self._tree.itemChanged.connect(self._on_item_changed)
        self.body_layout.addWidget(self._tree, 1)

        self._warning = QLabel(_WARNING_TEXT)
        self._warning.setObjectName("lblTimeframeWarning")
        self._warning.setWordWrap(True)
        self.body_layout.addWidget(self._warning)

        self._current = QLabel()
        self._current.setObjectName("lblTimeframeCurrent")
        self.body_layout.addWidget(self._current)

        selection.stateChanged.connect(self._render)
        selection.chosen.connect(self._on_chosen)
        self._render()

    @classmethod
    def from_callbacks(
        cls,
        *,
        get_codes: Callable[[], Sequence[str]],
        get_current: Callable[[], str],
        get_pinned: Callable[[], Sequence[str]],
        set_pinned: Callable[[str, bool], None],
        title: str = _DEFAULT_TITLE,
        parent: QWidget | None = None,
    ) -> TimeframePickerDialog:
        """Builds a private `TimeframeSelection` from four screen callbacks —
        the shape every caller but `ChartToolbar` uses, where this dialog is the
        only consumer of timeframe state."""
        selection = TimeframeSelection(
            get_codes=get_codes,
            get_current=get_current,
            get_pinned=get_pinned,
            set_pinned=set_pinned,
        )
        return cls(selection, title=title, parent=parent)

    # -- host-facing -------------------------------------------------------

    def open_dialog(self) -> None:
        """Re-reads codes, current and pinned, then shows.

        Public because a screen's offered codes and current choice both change
        between opens of one lazily-built dialog.
        """
        self._selection.refresh()
        self.show()
        self.raise_()

    def item_for(self, code: str) -> QTreeWidgetItem | None:
        """A row by its interval code, or `None` when it is not offered.

        Public so a consumer's test can pick or pin a row without walking this
        widget's private tree.
        """
        for index in range(self._tree.topLevelItemCount()):
            group = self._tree.topLevelItem(index)
            for child_index in range(group.childCount()):
                child = group.child(child_index)
                if child.data(_INTERVAL_COLUMN, _CODE_ROLE) == code:
                    return child
        return None

    # -- rendering ---------------------------------------------------------

    def _render(self) -> None:
        """Redraws from the selection, in place where it can.

        A rebuild here would be a crash, not an inefficiency: pinning a row
        reaches this method **from inside** that row's own `itemChanged`
        emission, and `QTreeWidget.clear()` would destroy the item whose signal
        is still being delivered — measured, as a segfault, the first time this
        widget's own test ticked a pin. `ChecklistOverlay.set_items()` learned
        the same thing one pull request earlier; here the case is easier,
        because pinning and choosing never change *which* intervals are
        offered, only their state.
        """
        if self._layout_signature() == self._rendered_signature:
            self._update_in_place()
        else:
            self._fill()
        self._warning.setVisible(self._selection.has_warning)
        self._current.setText(f"Current: {self._selection.current_code}")

    def _layout_signature(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """The structure a render would build: group labels and their codes.
        Equal signatures mean every row already on screen is still wanted."""
        return tuple(
            (group.label, tuple(row.code for row in group.rows))
            for group in self._selection.groups
        )

    def _update_in_place(self) -> None:
        for group in self._selection.groups:
            for row in group.rows:
                item = self.item_for(row.code)
                if item is None:  # pragma: no cover — signature guarantees one
                    continue
                self._write_row(item, row)

    def _write_row(self, item: QTreeWidgetItem, row) -> None:
        """Writes one row's state. `_filling` is raised around the check-state
        write, so the `itemChanged` it raises is not read back as a user
        ticking the pin."""
        was_filling = self._filling
        self._filling = True
        try:
            item.setCheckState(
                _PIN_COLUMN,
                Qt.CheckState.Checked if row.pinned else Qt.CheckState.Unchecked,
            )
        finally:
            self._filling = was_filling
        font = item.font(_INTERVAL_COLUMN)
        font.setBold(row.current)
        item.setFont(_INTERVAL_COLUMN, font)

    def _fill(self) -> None:
        self._filling = True
        try:
            self._tree.clear()
            for group in self._selection.groups:
                heading = QTreeWidgetItem([group.label, group.caption, ""])
                font = heading.font(_INTERVAL_COLUMN)
                font.setBold(True)
                heading.setFont(_INTERVAL_COLUMN, font)
                # A heading is not a row: it carries no code, so a click on it
                # chooses nothing and it has no pin box.
                self._tree.addTopLevelItem(heading)
                heading.setExpanded(True)
                for row in group.rows:
                    heading.addChild(self._row_item(row))
            self._rendered_signature = self._layout_signature()
        finally:
            self._filling = False

    def _row_item(self, row) -> QTreeWidgetItem:
        item = QTreeWidgetItem([row.code, row.label, ""])
        item.setData(_INTERVAL_COLUMN, _CODE_ROLE, row.code)
        self._write_row(item, row)
        return item

    # -- interaction -------------------------------------------------------

    def _on_activated(self, item: QTreeWidgetItem, column: int) -> None:
        """Keyboard activation (Enter, Space) picks the row it is on."""
        self._choose_from(item)

    def _on_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """A click picks the row — except on the pin column, whose own check
        box is the interaction there."""
        if column == _PIN_COLUMN:
            return
        self._choose_from(item)

    def _choose_from(self, item: QTreeWidgetItem) -> None:
        code = item.data(_INTERVAL_COLUMN, _CODE_ROLE)
        if isinstance(code, str) and code:
            self._selection.choose(code)

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._filling or column != _PIN_COLUMN:
            return
        code = item.data(_INTERVAL_COLUMN, _CODE_ROLE)
        if not isinstance(code, str) or not code:
            return
        pinned = item.checkState(_PIN_COLUMN) is Qt.CheckState.Checked
        # `toggle_pinned` flips whatever the selection currently holds, so it is
        # only called when the box disagrees with it — a re-render writing the
        # same state back must not flip it again.
        if pinned != self._is_pinned(code):
            self._selection.toggle_pinned(code)

    def _is_pinned(self, code: str) -> bool:
        return any(pill.code == code for pill in self._selection.pinned_rows)

    def _on_chosen(self, code: str) -> None:
        self.chosen.emit(code)
        self.accept()
