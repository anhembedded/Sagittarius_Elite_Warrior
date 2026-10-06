"""The event log's and progress bar's sentences about a run, written through
`AppValueFormatter` (`EPIC-033N`): a price, a count, a percent and a duration
read here as they do in a table, and the presenter, which is over its size
ceiling, only places them."""

from __future__ import annotations

from datetime import datetime

from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import write_value
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind


def money_text(amount: float) -> str:
    return write_value(ColumnKind.MONEY, amount)


def moment_text(moment: datetime | None, open_end: str) -> str:
    """A range's end as the application writes a timestamp; an open end by name."""
    return write_value(ColumnKind.TIMESTAMP, moment) if moment else open_end


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
