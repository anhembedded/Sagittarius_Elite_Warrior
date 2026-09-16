"""
@brief `TableCard` — a `Card` holding a column heading strip, a scrolling
body of rows, an empty state, and optional pagination.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum, auto

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..controls import StyledButton
from ..style import StyleRole, apply_role
from ..surface import Card
from .data_row import Column


class Pagination(Enum):
    """
    @brief How much paging chrome a table shows.

    @details Three values because the reference consumer's three tables have
    three answers, and `EPIC-007B`'s brief was to cover them rather than
    pick a winner. They are genuinely different affordances, not degrees:
    `SIMPLE` is for a table the user steps through, `FULL` for one they
    jump around in and resize, `NONE` for a list short enough that paging
    it would be noise.
    """

    NONE = auto()
    #: Previous / "page X of Y" / next. Hidden entirely while there is only
    #: one page, matching the consumer's trade log.
    SIMPLE = auto()
    #: First / previous / label / next / last, plus page-size buttons and a
    #: total count. Always visible, matching the consumer's candle
    #: inspector.
    FULL = auto()


#: The consumer's candle inspector offers exactly these. A default rather
#: than a required argument: a `FULL` table that never says otherwise gets
#: a sane set instead of an empty row of buttons.
_DEFAULT_PAGE_SIZES: tuple[int, ...] = (50, 100, 200, 500)


class TableCard(Card):
    """
    @brief A `Card` whose body is a heading strip over a scrolling list of
    rows, with an empty-state message and optional paging controls.

    @details
    **On the name.** `TableCard` was also the name of one of four QML stubs
    deleted in `EPIC-006` — deleted because they were guessed from a
    docstring and had zero instances between them, and because `setEnabled()`
    already did what they claimed to add. This class is the opposite case:
    three real tables exist today, all four of whose parts (heading strip
    built as its own frame from a column spec, a rows area, an empty label
    toggled on row count) are written out longhand in each. The name is
    reused because it is the right name, not because the old one was
    salvageable.

    **What genuinely unified, and what did not.** The heading strip did —
    all three build a frame of stretch-weighted labels from a column spec,
    and a fourth table elsewhere in the same app does too. Row storage did
    not: one uses a layout with a trailing stretch, one `setIndexWidget` on
    a real Qt model, one a layout plus a parallel Python list. This class
    owns the first and takes rows as widgets, leaving each consumer's
    storage strategy alone; `add_row`/`clear_rows` is the smallest surface
    that serves all three.

    **Paging is emitted, never performed.** `page_requested` and
    `page_size_requested` carry the user's intent; what the current page is
    remains the consumer's to decide and push back via `set_page`. The three
    consumers drive paging three ways — a view-model property assignment and
    two different request methods — and a card that tried to own the page
    number would fight all of them.
    """

    #: The page the user asked for, 1-based. Not clamped here: what the last
    #: page is belongs to whoever owns the data.
    page_requested = Signal(int)
    #: The rows-per-page the user picked. `FULL` mode only.
    page_size_requested = Signal(int)

    def __init__(
        self,
        title: str,
        columns: Sequence[Column],
        *,
        pagination: Pagination = Pagination.NONE,
        page_sizes: Sequence[int] = _DEFAULT_PAGE_SIZES,
        empty_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        if not columns:
            raise ValueError("TableCard needs at least one column")

        self._columns = tuple(columns)
        self._pagination = pagination
        self._current_page = 1
        self._total_pages = 1

        self.body_layout.addWidget(self._build_header())

        self._rows_host = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.addStretch(1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        apply_role(self._scroll, StyleRole.LIST_SURFACE)
        self._scroll.setWidget(self._rows_host)
        self.body_layout.addWidget(self._scroll, 1)

        self._empty_label = QLabel(empty_text)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body_layout.addWidget(self._empty_label)

        self._page_size_buttons: list[StyledButton] = []
        self._pagination_row = self._build_pagination(page_sizes)
        self.body_layout.addWidget(self._pagination_row)

        self._sync_rows_visibility()
        self._sync_pagination()

    @property
    def columns(self) -> tuple[Column, ...]:
        return self._columns

    @property
    def row_count(self) -> int:
        # The trailing stretch is not a row.
        return self._rows_layout.count() - 1

    @property
    def current_page(self) -> int:
        return self._current_page

    @property
    def total_pages(self) -> int:
        return self._total_pages

    def add_row(self, row: QWidget) -> None:
        """@brief Appends a row above the trailing stretch."""
        self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
        self._sync_rows_visibility()

    def clear_rows(self) -> None:
        """@brief Removes every row, keeping the trailing stretch."""
        while self._rows_layout.count() > 1:
            entry = self._rows_layout.takeAt(0)
            if entry is None:  # pragma: no cover — count() > 1 guarantees one
                break
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()
        self._sync_rows_visibility()

    def set_rows(self, rows: Sequence[QWidget]) -> None:
        """@brief Replaces every row in one call — the drain-and-refill each
        consumer currently writes by hand, in three different ways."""
        self.clear_rows()
        for row in rows:
            self.add_row(row)

    def set_page(self, current: int, total: int) -> None:
        """@brief Tells the card where the consumer decided the user now is."""
        self._current_page = current
        self._total_pages = total
        self._sync_pagination()

    def set_page_label(self, text: str) -> None:
        """@brief Overrides the page-position text. The default is
        `"{current} / {total}"`, which is language-neutral; a consumer
        wanting "Trang 2 / 7" sets it here rather than this package
        guessing at a language it cannot know."""
        self._page_label.setText(text)

    def set_count_text(self, text: str) -> None:
        """@brief Sets the total-records caption shown in `FULL` mode."""
        self._count_label.setText(text)
        self._count_label.setVisible(bool(text))

    def _build_header(self) -> QWidget:
        header = QWidget()
        apply_role(header, StyleRole.TABLE_HEADER)
        row = QHBoxLayout(header)
        for column in self._columns:
            label = QLabel(column.label)
            label.setAlignment(column.alignment | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(label, column.stretch)
        return header

    def _build_pagination(self, page_sizes: Sequence[int]) -> QWidget:
        host = QWidget()
        row = QHBoxLayout(host)

        self._count_label = QLabel()
        apply_role(self._count_label, StyleRole.CAPTION)
        self._count_label.setVisible(False)
        row.addWidget(self._count_label)
        row.addStretch(1)

        if self._pagination is Pagination.FULL:
            for size in page_sizes:
                button = StyledButton(str(size), role=StyleRole.SECONDARY_BUTTON)
                button.clicked.connect(
                    lambda _checked=False, s=size: self.page_size_requested.emit(s)
                )
                row.addWidget(button)
                self._page_size_buttons.append(button)

            self.first_button = self._nav_button("«", lambda: 1)
            row.addWidget(self.first_button)

        self.previous_button = self._nav_button("‹", lambda: self._current_page - 1)
        row.addWidget(self.previous_button)

        self._page_label = QLabel()
        row.addWidget(self._page_label)

        self.next_button = self._nav_button("›", lambda: self._current_page + 1)
        row.addWidget(self.next_button)

        if self._pagination is Pagination.FULL:
            self.last_button = self._nav_button("»", lambda: self._total_pages)
            row.addWidget(self.last_button)

        row.addStretch(1)
        return host

    def _nav_button(self, text: str, target) -> StyledButton:
        button = StyledButton(text, role=StyleRole.SECONDARY_BUTTON)
        button.clicked.connect(lambda: self.page_requested.emit(target()))
        return button

    def _sync_rows_visibility(self) -> None:
        has_rows = self.row_count > 0
        self._scroll.setVisible(has_rows)
        self._empty_label.setVisible(not has_rows)

    def _sync_pagination(self) -> None:
        if self._pagination is Pagination.NONE:
            self._pagination_row.setVisible(False)
            return
        # SIMPLE hides itself on a single page (the consumer's trade log
        # does); FULL stays put so its page-size buttons remain reachable
        # even when everything fits on one page (its candle inspector does).
        self._pagination_row.setVisible(
            self._pagination is Pagination.FULL or self._total_pages > 1
        )
        self._page_label.setText(f"{self._current_page} / {self._total_pages}")
        self.previous_button.setEnabled(self._current_page > 1)
        self.next_button.setEnabled(self._current_page < self._total_pages)
        if self._pagination is Pagination.FULL:
            self.first_button.setEnabled(self._current_page > 1)
            self.last_button.setEnabled(self._current_page < self._total_pages)
