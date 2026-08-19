from __future__ import annotations

from enum import Enum

from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)

from .trade_log_row import TradeLogRow


class TradeLogFilter(str, Enum):
    """@brief The 5 tabs above the Trade Logs table (BOT-057 §2.1)."""

    ALL = "all"
    LONG = "long"
    SHORT = "short"
    WIN = "win"
    LOSS = "loss"


def filter_trade_log_rows(
    rows: list[TradeLogRow], filter_: TradeLogFilter
) -> list[TradeLogRow]:
    """
    @brief Applies one of the 5 tab filters.
    @details `LONG`/`SHORT` read `TradeLogRow.side` since `BOT-050` gave
    `PaperExchange` real short-selling support — before that, this tab was a
    permanent no-op (kept selectable rather than hidden, an explicit task
    decision, so the UI wouldn't need reshaping once short-selling landed).
    """
    if filter_ is TradeLogFilter.ALL:
        return rows
    if filter_ is TradeLogFilter.LONG:
        return [row for row in rows if row.side is PositionSide.LONG]
    if filter_ is TradeLogFilter.SHORT:
        return [row for row in rows if row.side is PositionSide.SHORT]
    if filter_ is TradeLogFilter.WIN:
        return [row for row in rows if row.pnl > 0]
    if filter_ is TradeLogFilter.LOSS:
        return [row for row in rows if row.pnl < 0]
    raise ValueError(f"Unknown TradeLogFilter: {filter_!r}")


def search_trade_log_rows(rows: list[TradeLogRow], query: str) -> list[TradeLogRow]:
    """@brief Client-side substring match against the trade's display index
    (e.g. "#12", with or without the "#" — the mockup's own "mã lệnh" label)
    and its entry/exit dates — `Trade` has no order-id/symbol field distinct
    from the run's single symbol, so those are the only 2 things "mã lệnh,
    ngày..." (the search placeholder) can mean today."""
    needle = query.strip().lstrip("#").lower()
    if not needle:
        return rows
    return [
        row
        for row in rows
        if needle in str(row.index)
        or needle in row.entry_time.isoformat().lower()
        or needle in row.exit_time.isoformat().lower()
    ]
