"""
@brief `pick_date_range()` — opens the engine's `DateRangeOverlay` on the
app's own vocabulary and hands back the two strings its screens store.

@details
Both screens that pick a range keep it as free text in
`constants.DATETIME_FORMAT`, and both must keep doing so: the presenters
parse those strings, and a user who types rather than clicks is not losing
that. So this is a *bridge*, not a replacement — the fields stay, and this
adds a second way to fill them.

Lives in `components/` rather than either screen because both use it, per
`EPIC-007` §3's tier rule.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import DATETIME_FORMAT
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    DateRangeOverlay,
    RangePreset,
)

#: Vietnamese, because every string a user reads in this app is. The engine
#: ships English defaults precisely so a consumer replaces them.
_PRESETS: tuple[RangePreset, ...] = (
    RangePreset("Hôm nay", 0),
    RangePreset("7 ngày qua", 7),
    RangePreset("30 ngày qua", 30),
    RangePreset("90 ngày qua", 90),
    RangePreset("365 ngày qua", 365),
)
_WEEKDAYS = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")
_MONTH_NAME = "Tháng {month} {year}"

#: What the range falls back to when a field holds something unparseable —
#: the same week-long window `dashboard_view_model` already defaults to.
_FALLBACK_DAYS = 7

#: Minutes in a day. The summary counts one-minute candles because that is
#: the finest interval this app stores, so it is the ceiling a user is
#: really asking about when they size a range.
_MINUTES_PER_DAY = 1440


def _parse(raw: str) -> datetime | None:
    try:
        return datetime.strptime(raw.strip(), DATETIME_FORMAT).replace(tzinfo=UTC)
    except (ValueError, AttributeError):
        return None


def pick_date_range(
    parent: QWidget,
    *,
    start_text: str,
    end_text: str,
    title: str = "KHOẢNG THỜI GIAN DỮ LIỆU",
) -> tuple[str, str] | None:
    """
    @brief Opens the picker seeded from two strings; returns the chosen pair
    in the same format, or `None` when the user cancels.

    @details Unparseable input is not an error here. A half-typed date is
    the ordinary state of a text field, and refusing to open a calendar
    because of one is backwards — that is the moment a user most wants the
    calendar. It seeds a sensible week instead.
    """
    end = _parse(end_text) or datetime.now(UTC)
    start = _parse(start_text) or end - timedelta(days=_FALLBACK_DAYS)
    if start > end:
        start = end - timedelta(days=_FALLBACK_DAYS)

    overlay = DateRangeOverlay(
        title,
        start=start.date(),
        end=end.date(),
        presets=_PRESETS,
        weekday_names=_WEEKDAYS,
        month_name=_MONTH_NAME,
        confirm_text="Áp dụng",
        cancel_text="Hủy",
        parent=parent,
    )
    overlay.show_months_from(start.date() - timedelta(days=start.day - 1))
    _sync_summary(overlay)
    overlay.range_changed.connect(lambda *_: _sync_summary(overlay))

    if overlay.exec() != DateRangeOverlay.DialogCode.Accepted:
        return None
    chosen_start, chosen_end = overlay.selected_range
    if chosen_start is None or chosen_end is None:
        return None
    return (
        datetime.combine(chosen_start, start.timetz()).strftime(DATETIME_FORMAT),
        datetime.combine(chosen_end, end.timetz()).strftime(DATETIME_FORMAT),
    )


def _sync_summary(overlay: DateRangeOverlay) -> None:
    start, end = overlay.selected_range
    if start is None or end is None:
        overlay.summary = "Chọn ngày kết thúc"
        return
    days = (end - start).days
    overlay.summary = (
        f"{days} ngày · {start} → {end}   ≈ {days * _MINUTES_PER_DAY:,} nến 1m"
    )
