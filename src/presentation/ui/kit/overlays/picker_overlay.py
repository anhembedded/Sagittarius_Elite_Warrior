"""
@brief `PickerOverlay` — an `Overlay` offering one choice from a list of
`SelectableCard` rows, optionally filtered by a search field.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGridLayout, QLabel, QScrollArea, QWidget

from ..controls import StyledField
from ..overlay import Overlay
from ..style import StyleRole, apply_role
from ..surface import SelectableCard

#: `columns=1` renders the list shape (stacked label over subtitle), any
#: higher count renders the grid shape (one centred line per cell). Named
#: rather than compared against a bare 1 at three call sites.
_LIST_COLUMNS = 1


@dataclass(frozen=True)
class PickerItem:
    """
    @brief One offered choice: the `value` a consumer gets back, the `label`
    a user reads, and an optional `subtitle` line under it.

    @details The consuming app's six pickers each hold their options in a
    different shape — `list[str]`, and three different dict spellings
    (`key`/`name`, `value`/`label`, `id`/`label`). Rather than teach this
    class four vocabularies or take an extractor callback per picker, each
    consumer maps its own shape into this one. That keeps the variance in
    the code that owns the vocabulary.
    """

    value: str
    label: str
    subtitle: str = ""


class PickerOverlay(Overlay):
    """
    @brief An `Overlay` presenting `PickerItem`s as `SelectableCard`s in a
    list or an N-column grid, with an optional search field.

    @details
    **Choosing does not close the dialog.** `selection_changed` fires and
    `selected` updates; calling `accept()` is the consumer's move. Five of
    the app's six pickers do accept immediately, so closing here would look
    like the obvious default — but the sixth (its time-range picker) must
    stay open when "custom" is chosen, to reveal its own fields. A base that
    closed for them would need a flag to be told not to, and every consumer
    already writes that one line today.

    Single-select only. The app's indicator picker is multi-select, toggles
    checkboxes, and never closes — a genuinely different interaction, not a
    parameter of this one. Left as a candidate rather than guessed at, the
    lesson EPIC-006's four abandoned card stubs paid for.

    `set_items()` rebuilds the rows outright. The app repeats a manual
    drain-and-refill loop in eight places, always from `showEvent`, because
    the option list arrives asynchronously; this is that loop, written once.
    """

    #: Emits the chosen `PickerItem.value`. Not the `PickerItem` itself:
    #: `SelectableCard.clicked` carries no argument, so the value is
    #: captured per-row anyway, and every consumer wants the id it stores.
    selection_changed = Signal(str)

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        *,
        searchable: bool = False,
        search_placeholder: str = "",
        columns: int = _LIST_COLUMNS,
        empty_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        if columns < 1:
            raise ValueError(f"PickerOverlay columns must be >= 1, got {columns}")

        super().__init__(title, subtitle, parent=parent)

        # Every attribute `_rebuild()` reads is set before anything can call
        # it — `textChanged` is connected below, and hiding or placeholder-
        # setting a field does not emit it, but ordering this by hand is how
        # the ordering trap in `Overlay._build_buttons` got its own bug.
        self._columns = columns
        self._searchable = searchable
        self._items: list[PickerItem] = []
        self._selected: str | None = None

        self._search_field = StyledField()
        self._search_field.setPlaceholderText(search_placeholder)
        self._search_field.textChanged.connect(self._rebuild)
        self._search_field.setVisible(searchable)
        self.body_layout.addWidget(self._search_field)

        self._empty_label = QLabel(empty_text)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setVisible(False)
        self.body_layout.addWidget(self._empty_label)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._scroll = QScrollArea()
        apply_role(self._scroll, StyleRole.LIST_SURFACE)
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(self._grid_host)
        self.body_layout.addWidget(self._scroll, 1)

        self._rebuild()

    @property
    def selected(self) -> str | None:
        """The chosen `PickerItem.value`, or `None` while nothing is
        chosen."""
        return self._selected

    @selected.setter
    def selected(self, value: str | None) -> None:
        self._selected = value
        self._rebuild()

    def set_items(self, items: Sequence[PickerItem]) -> None:
        """@brief Replaces the offered choices and re-renders. Safe to call
        from `showEvent` on every open, which is how an asynchronously
        loaded option list reaches a picker."""
        self._items = list(items)
        self._rebuild()

    def _visible_items(self) -> list[PickerItem]:
        needle = self._search_field.text().strip().casefold()
        if not needle:
            return list(self._items)
        return [item for item in self._items if needle in item.label.casefold()]

    def _rebuild(self) -> None:
        while self._grid.count():
            entry = self._grid.takeAt(0)
            if entry is None:  # pragma: no cover — count() > 0 guarantees one
                break
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()

        has_items = bool(self._items)
        self._empty_label.setVisible(not has_items)
        self._scroll.setVisible(has_items)
        self._search_field.setVisible(self._searchable and has_items)

        for index, item in enumerate(self._visible_items()):
            card = self._build_card(item)
            # Default-arg capture, not a closure over `item`: `SelectableCard.
            # clicked` carries no argument, and a plain closure would hand
            # every row the last item of the loop.
            card.clicked.connect(lambda value=item.value: self._on_card_clicked(value))
            self._grid.addWidget(card, index // self._columns, index % self._columns)

    def _build_card(self, item: PickerItem) -> SelectableCard:
        card = SelectableCard()
        card.selected = item.value == self._selected

        label = QLabel(item.label)
        if self._columns > _LIST_COLUMNS:
            # Grid cells are single-line and centred; a subtitle has nowhere
            # to go in one, so it is dropped rather than silently squeezing
            # the cell taller than its neighbours.
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card.body_layout.addWidget(label)
            return card

        card.body_layout.addWidget(label)
        if item.subtitle:
            card.body_layout.addWidget(QLabel(item.subtitle))
        return card

    def _on_card_clicked(self, value: str) -> None:
        self._selected = value
        self._rebuild()
        self.selection_changed.emit(value)

    # `_build_buttons` is deliberately not overridden — `Overlay`'s default
    # empty row is the right footer here. None of the app's six pickers has
    # a Cancel or OK button; they are dismissed by choosing, or by the
    # window's own close control.
