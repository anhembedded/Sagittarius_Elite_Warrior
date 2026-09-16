"""
@brief `DateRangeOverlay` — an `Overlay` picking a start/end date pair from
a two-month calendar, with quick presets down the side.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..controls import StyledButton
from ..overlay import Overlay
from ..style import StyleRole, apply_role, semantic_colour

#: Monday-first. `calendar.Calendar(0)` below must stay in step with it —
#: they are the two halves of one decision about where a week starts.
_FIRST_WEEKDAY = 0

#: A month never spans more than six week-rows, and the grid is built to a
#: fixed six so switching months cannot change the dialog's height.
_WEEK_ROWS = 6

#: Months in a year — named because the paging arithmetic below wraps on it.
_MONTHS_IN_YEAR = 12


@dataclass(frozen=True)
class RangePreset:
    """
    @brief One entry in the quick-pick column: what a user reads, and the
    span it stands for.

    @details `days` is `None` for a preset with no fixed length — "all of
    history", "custom". The consumer resolves those, because only it knows
    where its data starts; this class will not guess a date it cannot know.
    """

    label: str
    days: int | None = None


#: What a date-range dialog offers when its consumer says nothing. Every
#: entry is a plain span; the two open-ended ones are deliberately absent,
#: since a default cannot resolve them.
DEFAULT_PRESETS: tuple[RangePreset, ...] = (
    RangePreset("Today", 0),
    RangePreset("Last 7 days", 7),
    RangePreset("Last 30 days", 30),
    RangePreset("Last 90 days", 90),
    RangePreset("Last 365 days", 365),
)


class _DayCell(QPushButton):
    """One day. Four renderings, and the reason they are not a `WidgetState`
    is that three of them describe a day's place in a *range* rather than a
    state the widget transitions through."""

    def __init__(self, day: date, *, outside: bool, edge: bool, inside: bool) -> None:
        super().__init__(str(day.day))
        self.date = day
        self.setFixedSize(32, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setEnabled(not outside)
        self.setStyleSheet(self._qss(outside=outside, edge=edge, inside=inside))

    @staticmethod
    def _qss(*, outside: bool, edge: bool, inside: bool) -> str:
        if outside:
            fg, bg, radius, weight = (
                semantic_colour("border"),
                "transparent",
                6,
                "normal",
            )
        elif edge:
            fg, bg, radius, weight = (
                semantic_colour("bg"),
                semantic_colour("accent"),
                6,
                "bold",
            )
        elif inside:
            # Square, so consecutive days meet with no seam and the range
            # reads as one band rather than a row of separate chips.
            fg, bg, radius, weight = (
                semantic_colour("textPrimary"),
                semantic_colour("stateActiveTint"),
                0,
                "normal",
            )
        else:
            fg, bg, radius, weight = (
                semantic_colour("textPrimary"),
                "transparent",
                6,
                "normal",
            )
        rule = (
            f"QPushButton{{color:{fg};background:{bg};border:0;"
            f"border-radius:{radius}px;font-family:monospace;font-size:12px;"
            f"font-weight:{weight};}}"
        )
        if edge or outside:
            return rule
        return rule + (
            f"QPushButton:hover{{background:{semantic_colour('stateHoverBg')};}}"
        )


class _MonthGrid(QWidget):  # base-exempt: a grid of day cells, not a surface
    """One month: its name, a weekday header row, and six week rows."""

    day_clicked = Signal(date)

    def __init__(
        self, weekday_names: Sequence[str], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)

        self._title = QLabel()
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        apply_role(self._title, StyleRole.TABLE_CELL_STRONG)
        column.addWidget(self._title)

        self._grid = QGridLayout()
        # No horizontal gap: the in-range band has to be continuous, and a
        # 2px gutter between cells breaks it into chips.
        self._grid.setHorizontalSpacing(0)
        self._grid.setVerticalSpacing(3)
        for index, name in enumerate(weekday_names):
            head = QLabel(name)
            head.setAlignment(Qt.AlignmentFlag.AlignCenter)
            apply_role(head, StyleRole.CAPTION)
            self._grid.addWidget(head, 0, index)
        column.addLayout(self._grid)
        column.addStretch(1)
        self._cells: list[_DayCell] = []

    @property
    def title(self) -> str:
        return self._title.text()

    def render_month(
        self, year: int, month: int, title: str, start: date | None, end: date | None
    ) -> None:
        """@brief Rebuilds the grid for one month, marking the range."""
        self._title.setText(title)
        for cell in self._cells:
            self._grid.removeWidget(cell)
            # `setParent(None)` as well as `deleteLater()`. Deletion is
            # queued, so a cell that is only scheduled for it keeps its
            # parent and keeps painting — the previous month's days stayed
            # on screen, overlapping the new ones and the weekday header.
            cell.setParent(None)
            cell.deleteLater()
        self._cells = []

        # `monthdatescalendar` gives five rows for a month that fits in
        # five, so taking it as-is made the grid 35 cells some months and 42
        # others — and the dialog changed height as the user paged, which is
        # exactly what the fixed row count is here to prevent. Extend from
        # the first cell instead, so the span is always six full weeks.
        weeks = calendar.Calendar(_FIRST_WEEKDAY).monthdatescalendar(year, month)
        first_cell = weeks[0][0]
        for row in range(_WEEK_ROWS):
            week = [
                first_cell + timedelta(days=row * 7 + offset) for offset in range(7)
            ]
            for position, day in enumerate(week):
                outside = day.month != month
                cell = _DayCell(
                    day,
                    outside=outside,
                    edge=not outside and day in (start, end),
                    inside=not outside
                    and start is not None
                    and end is not None
                    and start < day < end,
                )
                cell.clicked.connect(
                    lambda _checked=False, d=day: self.day_clicked.emit(d)
                )
                self._grid.addWidget(cell, row + 1, position)
                self._cells.append(cell)

    def cell_for(self, day: date) -> _DayCell | None:
        """@brief The cell showing `day`, or `None` when this month does not
        show it. For a consumer's tests, which otherwise have to reach into
        a layout by index and count weeks by hand."""
        for cell in self._cells:
            if cell.date == day and cell.isEnabled():
                return cell
        return None


class DateRangeOverlay(Overlay):
    """
    @brief An `Overlay` picking a start/end date pair: quick presets down
    the left, two months of calendar on the right, the chosen pair readable
    underneath.

    @details
    **Two months, not one.** Every range this exists to pick spans a month
    boundary more often than not, and a one-month calendar makes the user
    page back and forth to see both ends of their own selection.

    **Clicking does not close the dialog**, matching `PickerOverlay`: the
    first click sets the start and clears the end, the second sets the end.
    A consumer reads `selected_range` when its Confirm button fires.

    **The summary line is the consumer's sentence, not this class's.** It
    can count days, and it does; it cannot know that a day of one-minute
    candles is 1,440 rows, and it will not pretend to. `summary` is a plain
    string the consumer sets — the same split `Banner` and `StatCard` use,
    where this package owns the shape and the app owns the meaning.

    **Presets carry a span, not a date.** `RangePreset.days` is `None` for
    "all of history", because only the consumer knows where its data
    starts. Those fire `preset_chosen` and leave the range alone.
    """

    #: Emitted whenever the pair changes — by a click or by a preset. The
    #: end is `None` between the two clicks of a fresh selection.
    range_changed = Signal(object, object)

    #: Emitted when a preset with no fixed span is chosen, carrying its
    #: label. The consumer resolves it and calls `set_range`.
    preset_chosen = Signal(str)

    def __init__(
        self,
        title: str,
        *,
        start: date,
        end: date,
        presets: Sequence[RangePreset] = DEFAULT_PRESETS,
        weekday_names: Sequence[str] = ("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"),
        month_name: str = "",
        confirm_text: str = "Apply",
        cancel_text: str = "Cancel",
        parent: QWidget | None = None,
    ) -> None:
        """
        @param month_name A `str.format` template receiving `year` and
        `month`, e.g. `"Tháng {month} {year}"`. Empty falls back to the
        locale-independent `"{year}-{month:02d}"` — this package has no
        consuming app and therefore no language, the same reasoning
        `ConfirmOverlay`'s English defaults record.
        """
        self._start: date | None = start
        self._end: date | None = end
        self._anchor_month = date(start.year, start.month, 1)
        self._month_name = month_name or "{year}-{month:02d}"
        self._presets = tuple(presets)
        self._confirm_text = confirm_text
        self._cancel_text = cancel_text
        super().__init__(title, parent=parent)
        apply_role(self.title_label, StyleRole.HEADING)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self._build_presets())
        body.addLayout(self._build_calendars(weekday_names), 1)
        self.body_layout.addLayout(body)
        self._render()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    @property
    def selected_range(self) -> tuple[date | None, date | None]:
        return self._start, self._end

    def set_range(self, start: date, end: date) -> None:
        """@brief Sets both ends at once — what a consumer calls after
        resolving a preset this class could not resolve itself."""
        self._start, self._end = start, end
        self._anchor_month = date(start.year, start.month, 1)
        self._render()
        self.range_changed.emit(start, end)

    @property
    def summary(self) -> str:
        return self._summary.text()

    @summary.setter
    def summary(self, text: str) -> None:
        self._summary.setText(text)

    def show_months_from(self, first: date) -> None:
        """@brief Pages the calendar so `first`'s month is the left one."""
        self._anchor_month = date(first.year, first.month, 1)
        self._render()

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def _build_presets(self) -> QWidget:
        host = QWidget()
        host.setFixedWidth(180)
        column = QVBoxLayout(host)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(4)

        self._preset_buttons: list[QPushButton] = []
        for preset in self._presets:
            button = QPushButton(preset.label)
            button.setFixedHeight(34)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, p=preset: self._on_preset(p))
            column.addWidget(button)
            self._preset_buttons.append(button)
        column.addStretch(1)
        self._style_presets(selected=-1)
        return host

    def _build_calendars(self, weekday_names: Sequence[str]) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(14)

        months = QHBoxLayout()
        months.setSpacing(24)
        self._previous = self._nav_button("‹", -1)
        self._next = self._nav_button("›", +1)
        months.addWidget(self._previous, 0, Qt.AlignmentFlag.AlignTop)
        self._left_month = _MonthGrid(weekday_names)
        self._right_month = _MonthGrid(weekday_names)
        for grid in (self._left_month, self._right_month):
            grid.day_clicked.connect(self._on_day)
            months.addWidget(grid)
        months.addWidget(self._next, 0, Qt.AlignmentFlag.AlignTop)
        column.addLayout(months)
        column.addStretch(1)
        return column

    def _nav_button(self, glyph: str, step: int) -> QPushButton:
        button = QPushButton(glyph)
        button.setFixedSize(26, 26)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(
            f"QPushButton{{color:{semantic_colour('muted')};"
            f"background:{semantic_colour('stateIdleBg')};"
            f"border:1px solid {semantic_colour('border')};"
            f"border-radius:6px;font-size:13px;}}"
            f"QPushButton:hover{{color:{semantic_colour('textPrimary')};"
            f"border-color:{semantic_colour('accent')};}}"
        )
        button.clicked.connect(lambda _checked=False, s=step: self._page(s))
        return button

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        self._summary = QLabel()
        apply_role(self._summary, StyleRole.CAPTION)
        row.addWidget(self._summary)
        row.addStretch(1)

        self.cancel_button = StyledButton(
            self._cancel_text, role=StyleRole.SECONDARY_BUTTON
        )
        self.cancel_button.clicked.connect(self.reject)
        self.confirm_button = StyledButton(
            self._confirm_text, role=StyleRole.PRIMARY_BUTTON
        )
        self.confirm_button.clicked.connect(self.accept)
        row.addWidget(self.cancel_button)
        row.addWidget(self.confirm_button)
        return row

    # ------------------------------------------------------------------ #
    # Behaviour
    # ------------------------------------------------------------------ #

    def _on_day(self, day: date) -> None:
        # First click of a fresh pair sets the start and drops the end, so
        # the next click always has an unambiguous meaning. Clicking before
        # the current start restarts rather than inverting the pair.
        if self._end is not None or self._start is None or day < self._start:
            self._start, self._end = day, None
        else:
            self._end = day
        self._style_presets(selected=-1)
        self._render()
        self.range_changed.emit(self._start, self._end)

    def _on_preset(self, preset: RangePreset) -> None:
        self._style_presets(selected=self._presets.index(preset))
        if preset.days is None:
            self.preset_chosen.emit(preset.label)
            return
        # UTC, not `date.today()`: this app stores and reasons about
        # candles in UTC everywhere, and a local-midnight fallback would
        # silently shift a range by a day for anyone east of Greenwich.
        end = self._end or self._start or datetime.now(UTC).date()
        self.set_range(end - timedelta(days=preset.days), end)

    def _page(self, step: int) -> None:
        month = self._anchor_month.month + step
        year = self._anchor_month.year + (month - 1) // _MONTHS_IN_YEAR
        self._anchor_month = date(year, (month - 1) % _MONTHS_IN_YEAR + 1, 1)
        self._render()

    def _render(self) -> None:
        left = self._anchor_month
        right_month = left.month % _MONTHS_IN_YEAR + 1
        right_year = left.year + (1 if left.month == _MONTHS_IN_YEAR else 0)
        for grid, (year, month) in (
            (self._left_month, (left.year, left.month)),
            (self._right_month, (right_year, right_month)),
        ):
            grid.render_month(
                year,
                month,
                self._month_name.format(year=year, month=month),
                self._start,
                self._end,
            )

    def _style_presets(self, *, selected: int) -> None:
        for index, button in enumerate(self._preset_buttons):
            if index == selected:
                button.setStyleSheet(
                    f"QPushButton{{text-align:left;padding-left:12px;font-size:12px;"
                    f"border-radius:8px;color:{semantic_colour('textPrimary')};"
                    f"background:{semantic_colour('stateActiveTint')};"
                    f"border:1px solid {semantic_colour('accent')};}}"
                )
            else:
                button.setStyleSheet(
                    f"QPushButton{{text-align:left;padding-left:12px;font-size:12px;"
                    f"border-radius:8px;color:{semantic_colour('muted')};"
                    f"background:transparent;border:1px solid transparent;}}"
                    f"QPushButton:hover{{background:{semantic_colour('stateHoverBg')};"
                    f"color:{semantic_colour('textPrimary')};}}"
                )
