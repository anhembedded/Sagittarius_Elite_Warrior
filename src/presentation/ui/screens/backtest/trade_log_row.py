from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)

#: Matches `BackTestPresenter`'s `_CUSTOM_TIME_FORMAT` — reused here instead
#: of the mockup's Vietnamese "16 thg 7, 2026" cosmetic format, which has no
#: existing formatter anywhere else in this codebase and would only ever be
#: used in this one column.
_DATETIME_FORMAT = "%Y-%m-%d %H:%M"

#: `PaperExchange` (BOT-021) is long-only, single-position — every `Trade`
#: this engine ever produces IS an entry-then-exit long. There is no `side`
#: field on `Trade` to read (that's BOT-050's short-selling support), so this
#: label is a constant, not derived data.
_POSITION_LABEL = "vị thế mua"


@dataclass(frozen=True)
class TradeLogRow:
    """
    @brief Everything one row of the Trade Logs table needs, computed here
    so `BackTestTradeLogs.qml` stays a dumb renderer — same Presenter/View
    split as `StatCardData` (`performance_metrics_view.py`).

    @details `index` is the trade's 1-based position in the FULL,
    unfiltered `BacktestResult.trades` list — stable identity across
    filter/search/pagination, so "lệnh #12" always refers to the same trade
    no matter what the user currently has selected.
    """

    index: int
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    quantity: float
    pnl: float
    pnl_percent: float


def build_trade_log_rows(trades: list[Trade]) -> list[TradeLogRow]:
    """@brief 1-based-indexes `trades` in the order `PaperExchange` closed
    them — the ordering itself is not re-derived here, only labeled."""
    return [
        TradeLogRow(
            index=position,
            entry_time=trade.entry_time,
            entry_price=trade.entry_price,
            exit_time=trade.exit_time,
            exit_price=trade.exit_price,
            quantity=trade.quantity,
            pnl=trade.pnl,
            pnl_percent=trade.pnl_percent,
        )
        for position, trade in enumerate(trades, start=1)
    ]


def _format_datetime(value: datetime) -> str:
    return value.strftime(_DATETIME_FORMAT)


def _format_compact_usd(value: float) -> str:
    """@brief Mirrors the mockup's "0.96 K USD" compact notation for the
    Quy mô (position size) column — full precision would make wide numbers
    dominate a column meant to be scanned quickly, not read exactly."""
    if abs(value) >= 1000:
        return f"{value / 1000:,.2f} K USD"
    return f"{value:,.2f} USD"


def _signed_pnl(value: float, suffix: str) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:,.2f}{suffix}"


def trade_log_row_to_qml(row: TradeLogRow) -> dict[str, str]:
    """Converts to the plain-dict shape QML's `Repeater`/`ListView` model
    expects (camelCase keys, everything pre-formatted as display text —
    same boundary convention as `stat_cards_to_qml`)."""
    pnl_color = BULL_COLOR if row.pnl >= 0 else BEAR_COLOR
    position_value = row.quantity * row.entry_price
    return {
        "index": str(row.index),
        "positionLabel": f"#{row.index} {_POSITION_LABEL}",
        "entryTimeText": _format_datetime(row.entry_time),
        "exitTimeText": _format_datetime(row.exit_time),
        "entryPriceText": f"{row.entry_price:,.2f} USD",
        "exitPriceText": f"{row.exit_price:,.2f} USD",
        "positionSizeText": _format_compact_usd(position_value),
        "quantityText": f"{row.quantity:,.4g}",
        "pnlText": _signed_pnl(row.pnl, " USD"),
        "pnlColor": pnl_color,
        "returnText": _signed_pnl(row.pnl_percent, "%"),
    }


def trade_log_rows_to_qml(rows: list[TradeLogRow]) -> list[dict[str, str]]:
    return [trade_log_row_to_qml(row) for row in rows]
