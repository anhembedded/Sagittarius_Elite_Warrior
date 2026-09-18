from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum


class TimeRangePreset(str, Enum):
    """
    @brief The backtest window choices offered on the Backtest Screen toolbar
    (BOT-022 §3: "preset 7 / 30 / 90 / 365 ngày qua / Toàn bộ lịch sử / Tuỳ chỉnh").
    """

    LAST_7_DAYS = "7d"
    LAST_30_DAYS = "30d"
    LAST_90_DAYS = "90d"
    LAST_365_DAYS = "365d"
    ALL_HISTORY = "all"
    CUSTOM = "custom"


#: Only the fixed-length presets need a day count — ALL_HISTORY and CUSTOM
#: resolve their range differently (see resolve_time_range).
_PRESET_DAYS: dict[TimeRangePreset, int] = {
    TimeRangePreset.LAST_7_DAYS: 7,
    TimeRangePreset.LAST_30_DAYS: 30,
    TimeRangePreset.LAST_90_DAYS: 90,
    TimeRangePreset.LAST_365_DAYS: 365,
}


def resolve_time_range(
    preset: TimeRangePreset,
    now: datetime,
    custom_start: datetime | None = None,
    custom_end: datetime | None = None,
) -> tuple[datetime | None, datetime | None]:
    """
    @brief Turns a preset choice into the `(start_time, end_time)` pair
    `RunStaticBacktestCommand` expects.
    @details `ALL_HISTORY` maps to `(None, None)` — the command/handler
    already treat a missing bound as "no limit" (`IMarketDataRepository`
    fetches everything available). `CUSTOM` passes through whatever the user
    entered untouched, including `None` for an unfilled field — the caller
    validates those, this function only resolves the mapping.
    """
    if preset is TimeRangePreset.ALL_HISTORY:
        return None, None
    if preset is TimeRangePreset.CUSTOM:
        return custom_start, custom_end
    return now - timedelta(days=_PRESET_DAYS[preset]), now
