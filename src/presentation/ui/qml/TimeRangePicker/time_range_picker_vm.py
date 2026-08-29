"""State and calendar math behind `TimeRangePicker.qml`.

Generalises `kit/overlays/date_range_overlay.py`'s `DateRangeOverlay` (presets
+ two-month calendar) to the QML widget shape (`EPIC-015` §1): every rule a
`.qml` file would otherwise need an `if`/loop for lives here instead, as
plain data the view only binds to (§1.2). Unlike `SymbolPickerVM`, this
widget is callback-constructed like `SelectListVM`/`CapitalVM` — it is meant
to be hosted inside `QmlOverlay` by whichever screen needs it (Data
Management, Dev Board, ...), not to be portable to another Qt application,
so it has no reason to invent its own `ISource` ABC.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, time, timedelta
from enum import Enum

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import DATETIME_FORMAT

#: Monday-first, matching `DateRangeOverlay`'s `_FIRST_WEEKDAY`.
_FIRST_WEEKDAY = 0
_WEEK_ROWS = 6
_MONTHS_IN_YEAR = 12
_FALLBACK_DAYS = 7
_DEFAULT_WEEKDAY_LABELS: tuple[str, ...] = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")
_DEFAULT_MONTH_LABEL = "Tháng {month} {year}"


class _PresetKind(str, Enum):
    TODAY = "today"
    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"
    LAST_365_DAYS = "365d"
    ALL_HISTORY = "all"
    CUSTOM = "custom"


_PRESET_ORDER: tuple[_PresetKind, ...] = (
    _PresetKind.TODAY,
    _PresetKind.LAST_7_DAYS,
    _PresetKind.LAST_30_DAYS,
    _PresetKind.LAST_90_DAYS,
    _PresetKind.LAST_365_DAYS,
    _PresetKind.ALL_HISTORY,
    _PresetKind.CUSTOM,
)

_PRESET_LABELS: dict[_PresetKind, str] = {
    _PresetKind.TODAY: "Hôm nay",
    _PresetKind.LAST_7_DAYS: "7 ngày qua",
    _PresetKind.LAST_30_DAYS: "30 ngày qua",
    _PresetKind.LAST_90_DAYS: "90 ngày qua",
    _PresetKind.LAST_365_DAYS: "365 ngày qua",
    _PresetKind.ALL_HISTORY: "Toàn bộ lịch sử",
    _PresetKind.CUSTOM: "Tuỳ chỉnh",
}

#: Only the fixed-length presets need a day count — ALL_HISTORY resolves to
#: `(None, None)` (the "no limit" convention `resolve_time_range` already
#: uses for the backend) and CUSTOM leaves whatever is already selected.
_PRESET_DAYS: dict[_PresetKind, int] = {
    _PresetKind.TODAY: 0,
    _PresetKind.LAST_7_DAYS: 7,
    _PresetKind.LAST_30_DAYS: 30,
    _PresetKind.LAST_90_DAYS: 90,
    _PresetKind.LAST_365_DAYS: 365,
}


def _parse(raw: str) -> datetime | None:
    try:
        return datetime.strptime(raw.strip(), DATETIME_FORMAT).replace(tzinfo=UTC)
    except (ValueError, AttributeError):
        return None


class TimeRangePickerVM(QObject):
    """
    @brief A start/end instant pair, chosen by preset, calendar click, or
    typed text — all three write the same two fields.

    @details Callback-constructed, not handed a screen ViewModel — same
    reasoning as `SelectListVM`: this widget has no opinion about which
    screen owns it. `get_timeframe_seconds`/`get_timeframe_label` are what
    let the summary read "≈ N nến 5m" instead of a value hardcoded to one
    interval — the previous QtWidgets bridge (`components/date_range_picker.py`)
    always said "nến 1m" regardless of what a screen actually stores.
    """

    stateChanged = Signal()
    applied = Signal(str, str)

    def __init__(
        self,
        *,
        get_now: Callable[[], datetime],
        get_from_text: Callable[[], str],
        get_to_text: Callable[[], str],
        get_timeframe_seconds: Callable[[], int],
        get_timeframe_label: Callable[[], str],
        weekday_labels: Sequence[str] = _DEFAULT_WEEKDAY_LABELS,
        month_label: str = _DEFAULT_MONTH_LABEL,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_now = get_now
        self._get_from_text = get_from_text
        self._get_to_text = get_to_text
        self._get_timeframe_seconds = get_timeframe_seconds
        self._get_timeframe_label = get_timeframe_label
        self._weekday_labels = tuple(weekday_labels)
        self._month_label = month_label

        self._start: datetime | None = None
        self._end: datetime | None = None
        self._preset: str = _PresetKind.CUSTOM.value
        self._anchor = datetime.now(UTC).date().replace(day=1)

        self._presets_rows: list[dict[str, object]] = []
        self._left_label = ""
        self._right_label = ""
        self._left_days: list[dict[str, object]] = []
        self._right_days: list[dict[str, object]] = []
        self._from_text = ""
        self._to_text = ""
        self._summary = ""
        self._can_apply = False

    # ------------------------------------------------------------------ #
    # QML-facing properties — all recompute together, see `_recompute`.
    # ------------------------------------------------------------------ #

    @Property("QVariantList", notify=stateChanged)
    def presets(self) -> list[dict[str, object]]:
        return self._presets_rows

    @Property(str, notify=stateChanged)
    def leftMonthLabel(self) -> str:
        return self._left_label

    @Property(str, notify=stateChanged)
    def rightMonthLabel(self) -> str:
        return self._right_label

    @Property("QVariantList", notify=stateChanged)
    def leftDays(self) -> list[dict[str, object]]:
        return self._left_days

    @Property("QVariantList", notify=stateChanged)
    def rightDays(self) -> list[dict[str, object]]:
        return self._right_days

    @Property("QVariantList", constant=True)
    def weekdayLabels(self) -> list[str]:
        return list(self._weekday_labels)

    @Property(str, notify=stateChanged)
    def fromText(self) -> str:
        return self._from_text

    @Property(str, notify=stateChanged)
    def toText(self) -> str:
        return self._to_text

    @Property(str, notify=stateChanged)
    def summaryText(self) -> str:
        return self._summary

    @Property(bool, notify=stateChanged)
    def canApply(self) -> bool:
        return self._can_apply

    # ------------------------------------------------------------------ #
    # Host-facing API
    # ------------------------------------------------------------------ #

    def refresh(self) -> None:
        """Reloads the seed range from the host and rebuilds everything."""
        now = self._get_now()
        start = _parse(self._get_from_text())
        end = _parse(self._get_to_text())
        if start is None or end is None or start > end:
            end = end or now
            start = start or (end - timedelta(days=_FALLBACK_DAYS))
        self._start, self._end = start, end
        self._preset = _PresetKind.CUSTOM.value
        self._anchor = date(start.year, start.month, 1)
        self._recompute()

    @Slot(str)
    def choosePreset(self, preset_id: str) -> None:
        try:
            kind = _PresetKind(preset_id)
        except ValueError:
            return
        self._preset = kind.value
        if kind is _PresetKind.ALL_HISTORY:
            self._start, self._end = None, None
        elif kind is not _PresetKind.CUSTOM:
            now = self._get_now()
            # `days=0` ("Hôm nay") intentionally yields `start == end` — the
            # same single-instant convention `DateRangeOverlay.DEFAULT_PRESETS`
            # already uses; a "midnight to now" definition would be a second,
            # different meaning of "today" this app does not otherwise have.
            self._end = now
            self._start = now - timedelta(days=_PRESET_DAYS[kind])
        if self._start is not None:
            self._anchor = date(self._start.year, self._start.month, 1)
        self._recompute()

    @Slot(str)
    def selectDay(self, iso: str) -> None:
        try:
            day = date.fromisoformat(iso)
        except ValueError:
            return
        start_date = self._start.date() if self._start else None
        # First click of a fresh pair sets the start and drops the end, so
        # the next click always has an unambiguous meaning — same rule
        # `DateRangeOverlay._on_day` uses.
        if self._end is not None or start_date is None or day < start_date:
            self._start = datetime.combine(
                day, self._start.time() if self._start else time(0, 0), tzinfo=UTC
            )
            self._end = None
        else:
            self._end = datetime.combine(
                day, self._end.time() if self._end else time(23, 59), tzinfo=UTC
            )
        self._preset = _PresetKind.CUSTOM.value
        self._recompute()

    @Slot(int)
    def pageMonths(self, step: int) -> None:
        month = self._anchor.month + step
        year = self._anchor.year + (month - 1) // _MONTHS_IN_YEAR
        self._anchor = date(year, (month - 1) % _MONTHS_IN_YEAR + 1, 1)
        self._recompute()

    @Slot(str)
    def setFromText(self, text: str) -> None:
        self._start = _parse(text)
        self._preset = _PresetKind.CUSTOM.value
        if self._start is not None:
            self._anchor = date(self._start.year, self._start.month, 1)
        self._recompute()

    @Slot(str)
    def setToText(self, text: str) -> None:
        self._end = _parse(text)
        self._preset = _PresetKind.CUSTOM.value
        self._recompute()

    @Slot()
    def apply(self) -> None:
        if not self._can_apply:
            return
        from_text = self._start.strftime(DATETIME_FORMAT) if self._start else ""
        to_text = self._end.strftime(DATETIME_FORMAT) if self._end else ""
        self.applied.emit(from_text, to_text)

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _recompute(self) -> None:
        self._presets_rows = [
            {
                "id": kind.value,
                "label": _PRESET_LABELS[kind],
                "selected": kind.value == self._preset,
            }
            for kind in _PRESET_ORDER
        ]
        right_month = self._anchor.month % _MONTHS_IN_YEAR + 1
        right_year = self._anchor.year + (
            1 if self._anchor.month == _MONTHS_IN_YEAR else 0
        )
        self._left_label = self._month_label.format(
            year=self._anchor.year, month=self._anchor.month
        )
        self._right_label = self._month_label.format(year=right_year, month=right_month)
        self._left_days = self._month_cells(self._anchor.year, self._anchor.month)
        self._right_days = self._month_cells(right_year, right_month)
        self._from_text = self._start.strftime(DATETIME_FORMAT) if self._start else ""
        self._to_text = self._end.strftime(DATETIME_FORMAT) if self._end else ""
        self._summary = self._build_summary()
        self._can_apply = not ((self._start is None) ^ (self._end is None))
        self.stateChanged.emit()

    def _month_cells(self, year: int, month: int) -> list[dict[str, object]]:
        # Extend from the first cell to a fixed six weeks, same reasoning as
        # `_MonthGrid.render_month`: a plain `monthdatescalendar()` gives five
        # rows some months and six others, and the dialog would change height
        # paging between them.
        weeks = calendar.Calendar(_FIRST_WEEKDAY).monthdatescalendar(year, month)
        first_cell = weeks[0][0]
        start_date = self._start.date() if self._start else None
        end_date = self._end.date() if self._end else None
        cells: list[dict[str, object]] = []
        for row in range(_WEEK_ROWS):
            for offset in range(7):
                day = first_cell + timedelta(days=row * 7 + offset)
                outside = day.month != month
                edge = not outside and day in (start_date, end_date)
                inside = (
                    not outside
                    and start_date is not None
                    and end_date is not None
                    and start_date < day < end_date
                )
                cells.append(
                    {
                        "iso": day.isoformat(),
                        "day": day.day,
                        "outside": outside,
                        "edge": edge,
                        "inside": inside,
                    }
                )
        return cells

    def _build_summary(self) -> str:
        if self._start is None and self._end is None:
            return "Toàn bộ lịch sử · không giới hạn"
        if self._start is None:
            return "Chọn ngày bắt đầu"
        if self._end is None:
            return "Chọn ngày kết thúc"
        days = max((self._end.date() - self._start.date()).days, 0)
        seconds = max(int(self._get_timeframe_seconds()), 1)
        candles = int(days * 86400 / seconds)
        label = self._get_timeframe_label()
        return (
            f"{days} ngày · {self._start.date()} → {self._end.date()}"
            f"   ≈ {candles:,} nến {label}"
        )
