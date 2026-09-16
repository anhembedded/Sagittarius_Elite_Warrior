"""`TimeRangePickerDialog` — pick a start and an end. Shared by three screens.

## What this replaces, and the two implementations it ends

Data Management, Dev Board and Backtest all open the same picker, and until
`EPIC-025` PR 4.3d the app had **two** of them:

  · `kit/overlays/date_range_overlay.py` — QtWidgets, 454 lines, one
    `QPushButton` per day with an inline stylesheet on each. Dead in `src/`
    since `EPIC-015`, alive only in the developer showcase; **deleted in PR
    4.3c**.
  · `qml/TimeRangePicker/` — the same calendar again, its cells computed in
    Python (`leftDays`, `rightDays`, `_month_cells`, `pageMonths`) so a `.qml`
    file could bind to them. **Deleted here.**

Both hand-drew a calendar. `QCalendarWidget` is a calendar, ADR D20 forbids the
substitute, and HLD §11.3 maps this exact widget — *"time-range and timeframe
pickers"* — to a dialog.

## Two calendars, and that removes a rule rather than porting it

The old pickers showed **one** two-month grid serving both ends, so a click had
to be disambiguated: *"first click of a fresh pair sets the start and drops the
end, so the next click always has an unambiguous meaning"* — a rule both
implementations carried, and which existed only because one grid did two jobs.

Two `QCalendarWidget`s, one labelled From and one To, make the question
disappear: the user clicks in the calendar for the end they mean. The rule is
**not** ported, because there is nothing left for it to disambiguate.

## What is still this dialog's own

The presets, the summary line and the "both ends or neither" validation, all of
which live in `range_rules.py` with no widget attached. This file is the
wiring: which control writes which end, and keeping the calendars, the
`DateTimeField`s and the summary showing the same pair.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from PySide6.QtCore import QDate, QDateTime, Qt, Signal
from PySide6.QtWidgets import (
    QCalendarWidget,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import DateTimeField, Overlay

from .range_rules import (
    PRESET_LABELS,
    PRESET_ORDER,
    RangePresetKind,
    build_summary,
    can_apply,
    format_instant,
    resolve_preset,
    seed_range,
)

_DEFAULT_TITLE = "DATA TIME RANGE"
_FROM_LABEL = "From"
_TO_LABEL = "To"


def _default_get_now() -> datetime:
    return datetime.now(UTC)


def _to_qdatetime(value: datetime) -> QDateTime:
    return QDateTime.fromString(
        value.strftime("%Y-%m-%d %H:%M:%S"), "yyyy-MM-dd HH:mm:ss"
    )


def _from_qdatetime(value: QDateTime) -> datetime:
    return datetime(
        value.date().year(),
        value.date().month(),
        value.date().day(),
        value.time().hour(),
        value.time().minute(),
        value.time().second(),
        tzinfo=UTC,
    )


class TimeRangePickerDialog(Overlay):
    """
    @brief A start and an end instant, chosen by preset, calendar or typed
    text — all three write the same two values.

    @param get_from_text / get_to_text The screen's current pair, as
        `constants.DATETIME_FORMAT` text.
    @param get_timeframe_seconds / get_timeframe_label What lets the summary
        read "≈ N candles 5m" for the screen's *actual* timeframe rather than a
        value hardcoded to one interval.
    @param get_now Defaults to `datetime.now(UTC)`; overridable for tests that
        need a fixed clock.
    """

    applied = Signal(str, str)

    def __init__(
        self,
        *,
        get_from_text: Callable[[], str],
        get_to_text: Callable[[], str],
        get_timeframe_seconds: Callable[[], int],
        get_timeframe_label: Callable[[], str],
        get_now: Callable[[], datetime] = _default_get_now,
        title: str = _DEFAULT_TITLE,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent=parent)
        self.setObjectName("timeRangePickerDialog")
        self.resize(720, 480)

        self._get_from_text = get_from_text
        self._get_to_text = get_to_text
        self._get_timeframe_seconds = get_timeframe_seconds
        self._get_timeframe_label = get_timeframe_label
        self._get_now = get_now

        self._start: datetime | None = None
        self._end: datetime | None = None
        self._preset = RangePresetKind.CUSTOM
        #: Set while a control is being written from `_sync_controls()`, so the
        #: signal that write raises does not come back round as a user edit.
        self._syncing = False

        self._build_presets()
        self._build_calendars()
        self._build_fields()
        self._build_summary_row()

    # -- construction ------------------------------------------------------

    def _build_presets(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(6)
        self._preset_buttons: dict[RangePresetKind, QPushButton] = {}
        for kind in PRESET_ORDER:
            button = QPushButton(PRESET_LABELS[kind])
            button.setObjectName(f"btnTimeRangePreset_{kind.value}")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, k=kind: self._choose_preset(k)
            )
            row.addWidget(button)
            self._preset_buttons[kind] = button
        row.addStretch(1)
        self.body_layout.addLayout(row)

    def _build_calendars(self) -> None:
        grid = QGridLayout()
        grid.setSpacing(8)
        self._from_calendar = self._calendar("calFrom", self._on_from_date)
        self._to_calendar = self._calendar("calTo", self._on_to_date)
        grid.addWidget(self._heading(_FROM_LABEL), 0, 0)
        grid.addWidget(self._heading(_TO_LABEL), 0, 1)
        grid.addWidget(self._from_calendar, 1, 0)
        grid.addWidget(self._to_calendar, 1, 1)
        self.body_layout.addLayout(grid, 1)

    def _calendar(self, name: str, on_clicked: Callable[[QDate], None]):
        calendar = QCalendarWidget()
        calendar.setObjectName(name)
        # Monday first, matching every previous version of this dialog.
        calendar.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        calendar.setGridVisible(True)
        # Qt's own week numbers, not ours to draw.
        calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        calendar.clicked.connect(on_clicked)
        return calendar

    def _build_fields(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        self._from_field = DateTimeField()
        self._from_field.setObjectName("fldTimeRangeFrom")
        self._from_field.dateTimeChanged.connect(self._on_from_field)
        self._to_field = DateTimeField()
        self._to_field.setObjectName("fldTimeRangeTo")
        self._to_field.dateTimeChanged.connect(self._on_to_field)
        row.addWidget(self._heading(_FROM_LABEL))
        row.addWidget(self._from_field, 1)
        row.addWidget(self._heading(_TO_LABEL))
        row.addWidget(self._to_field, 1)
        self.body_layout.addLayout(row)

    def _build_summary_row(self) -> None:
        self._summary_label = QLabel()
        self._summary_label.setObjectName("lblTimeRangeSummary")
        self.body_layout.addWidget(self._summary_label)

    @staticmethod
    def _heading(text: str) -> QLabel:
        """A plain `QLabel`, deliberately.

        `apply_role(..., StyleRole.CAPTION)` is what every other dialog in this
        repository would use here, and this one does not: `apply_role` **is**
        the app's own styling layer, HLD §11.4 deletes it in this phase, and
        `test_app_styling_only_shrinks.py` holds those four numbers shrink-only.
        A widget written *in* Phase 4 that added to the count it exists to drive
        to zero would be raising a ratchet with a new file, which
        `ci-rule.md` §5.5 forbids outright. It renders in the OS theme, which is
        the target state (ADR D21).
        """
        return QLabel(text)

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("btnCancelTimeRange")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        self._btn_apply = QPushButton("Apply")
        self._btn_apply.setObjectName("btnApplyTimeRange")
        self._btn_apply.setDefault(True)
        self._btn_apply.clicked.connect(self._apply)
        row.addWidget(self._btn_apply)
        return row

    # -- host-facing -------------------------------------------------------

    def open_dialog(self) -> None:
        self.refresh()
        self.show()
        self.raise_()

    def showEvent(self, event) -> None:
        """Reseeds on every open: the host's pair can change between opens, and
        a scan can fill in a range the dialog opened without."""
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        """Re-reads the host's pair and redraws."""
        self._start, self._end = seed_range(
            self._get_from_text(), self._get_to_text(), self._get_now()
        )
        self._preset = RangePresetKind.CUSTOM
        self._sync_controls()

    # -- interaction -------------------------------------------------------

    def _choose_preset(self, kind: RangePresetKind) -> None:
        self._preset = kind
        resolved = resolve_preset(kind, self._get_now())
        if resolved is not None:
            self._start, self._end = resolved
        self._sync_controls()

    def _on_from_date(self, day: QDate) -> None:
        if self._syncing:
            return
        self._start = self._combine(day, self._start, fallback_hour=0)
        self._preset = RangePresetKind.CUSTOM
        self._sync_controls()

    def _on_to_date(self, day: QDate) -> None:
        if self._syncing:
            return
        self._end = self._combine(day, self._end, fallback_hour=23, fallback_minute=59)
        self._preset = RangePresetKind.CUSTOM
        self._sync_controls()

    def _on_from_field(self, value: QDateTime) -> None:
        if self._syncing:
            return
        self._start = _from_qdatetime(value)
        self._preset = RangePresetKind.CUSTOM
        self._sync_controls()

    def _on_to_field(self, value: QDateTime) -> None:
        if self._syncing:
            return
        self._end = _from_qdatetime(value)
        self._preset = RangePresetKind.CUSTOM
        self._sync_controls()

    @staticmethod
    def _combine(
        day: QDate,
        existing: datetime | None,
        *,
        fallback_hour: int,
        fallback_minute: int = 0,
    ) -> datetime:
        """A clicked day keeps whatever time that end already had.

        Clicking a date must not silently move the clock: a user who typed
        09:30 and then corrected the date meant 09:30 on the new date. Only an
        end that had no time yet gets the fallback — start of day for `From`,
        23:59 for `To`, which is what both previous pickers used.
        """
        return datetime(
            day.year(),
            day.month(),
            day.day(),
            existing.hour if existing else fallback_hour,
            existing.minute if existing else fallback_minute,
            tzinfo=UTC,
        )

    def _apply(self) -> None:
        if not can_apply(self._start, self._end):
            return
        self.applied.emit(format_instant(self._start), format_instant(self._end))
        self.accept()

    # -- rendering ---------------------------------------------------------

    def _sync_controls(self) -> None:
        """One place writes every control, so they cannot disagree.

        `_syncing` is what stops a write here from arriving back as a user
        edit: `setSelectedDate` and `setDateTime` both raise their change
        signal, and without the guard choosing a preset would immediately
        overwrite itself with `CUSTOM`.
        """
        self._syncing = True
        try:
            for kind, button in self._preset_buttons.items():
                button.setChecked(kind is self._preset)

            has_range = self._start is not None and self._end is not None
            for calendar, field, value in (
                (self._from_calendar, self._from_field, self._start),
                (self._to_calendar, self._to_field, self._end),
            ):
                calendar.setEnabled(has_range)
                field.setEnabled(has_range)
                if value is not None:
                    calendar.setSelectedDate(QDate(value.year, value.month, value.day))
                    field.setDateTime(_to_qdatetime(value))

            # `build_summary` already words every state, "all history"
            # included; a second string here for the same state was two places
            # to change one sentence.
            self._summary_label.setText(
                build_summary(
                    self._start,
                    self._end,
                    timeframe_seconds=self._get_timeframe_seconds(),
                    timeframe_label=self._get_timeframe_label(),
                )
            )
            self._btn_apply.setEnabled(can_apply(self._start, self._end))
        finally:
            self._syncing = False
