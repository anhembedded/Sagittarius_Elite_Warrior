"""The event log's and progress bar's sentences about a run, written through
`AppValueFormatter` (`EPIC-033N`): a price, a count, a percent and a duration
read here as they do in a table, and the presenter, which is over its size
ceiling, only places them."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    resolve_zone_info,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    AppValueFormatter,
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    FormatContext,
)

if TYPE_CHECKING:
    from .backtest_fsm_matrix import BacktestRunConfig


def money_text(amount: float) -> str:
    return write_value(ColumnKind.MONEY, amount)


def zone_name(time_zone: str) -> str:
    """The zone `time_zone` really resolves to, by name ("UTC" when the setting cannot be
    resolved): a text that names its zone must name the one it was written in."""
    return resolve_zone_info(time_zone).key


def moment_in_zone(moment: datetime, time_zone: str = DEFAULT_TIMEZONE) -> str:
    """`BOT-162` — a moment as the trades table writes it, in the display time zone the person chose
    (`ZonedValueFormatter`), with no zone named."""
    return AppValueFormatter(time_zone).format(
        ColumnKind.TIMESTAMP, moment, FormatContext(ColumnKind.TIMESTAMP.value)
    )


def zone_suffix(time_zone: str, *, name_utc: bool = False) -> str:
    """` <zone>` for a text that is not in UTC, else nothing (the text reads as it always did);
    `name_utc` for a sentence that already said "UTC". A text is not rewritten when the person
    changes the zone, so one written in another zone must name it to stay true."""
    zone = zone_name(time_zone)
    return "" if zone == DEFAULT_TIMEZONE and not name_utc else f" {zone}"


def zoned_moment_text(
    moment: datetime, time_zone: str = DEFAULT_TIMEZONE, *, name_utc: bool = False
) -> str:
    return moment_in_zone(moment, time_zone) + zone_suffix(time_zone, name_utc=name_utc)


def moment_text(
    moment: datetime | None, open_end: str, time_zone: str = DEFAULT_TIMEZONE
) -> str:
    """A range's end in the display zone, with no zone named; an open end by name."""
    return moment_in_zone(moment, time_zone) if moment else open_end


def time_range_diff_text(
    before: BacktestRunConfig, after: BacktestRunConfig, time_zone: str
) -> str:
    """`Time range (a..b → c..d)` for the config diff, in the display time zone, which it
    names once, after the range, unless it is UTC (`BOT-162`). An open start reads "Start", an open end "Now"."""

    def written(config: BacktestRunConfig) -> str:
        start = moment_text(config.start_time, "Start", time_zone)
        return f"{start}..{moment_text(config.end_time, 'Now', time_zone)}"

    suffix = zone_suffix(time_zone)
    named = f" in{suffix}" if suffix else ""
    return f"Time range ({written(before)} → {written(after)}){named}"


def signal_text(side: str, symbol: str, price: float) -> str:
    """`Signal: BUY BTCUSDT @ 64,250.10` — what the strategy asked for."""
    return f"Signal: {side.upper()} {symbol} @ {write_value(ColumnKind.PRICE, price)}"


def completed_event_text(trade_count: int, duration_seconds: float) -> str:
    return (
        f"Backtest completed: {write_value(ColumnKind.QUANTITY, trade_count)} trades "
        f"(duration: {write_value(ColumnKind.DURATION, duration_seconds)})"
    )


def progress_text(phase: str, percent: float, eta_seconds: int | None) -> str:
    """`Testing in-sample: 42.00% · ETA ~0:00:12`; no ETA before a first bar."""
    eta = (
        f" · ETA ~{write_value(ColumnKind.DURATION, eta_seconds)}"
        if eta_seconds is not None
        else ""
    )
    return f"{phase}: {write_value(ColumnKind.PERCENT, percent)}{eta}"


def sync_text(current: int, total: int, percent: float) -> str:
    """`Syncing candles: 1,200/5,000 (24.00%)`."""
    return (
        f"Syncing candles: {write_value(ColumnKind.QUANTITY, current)}"
        f"/{write_value(ColumnKind.QUANTITY, total)} "
        f"({write_value(ColumnKind.PERCENT, percent)})"
    )
