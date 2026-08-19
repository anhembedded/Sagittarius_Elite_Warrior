from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.domain.backtesting.exit_reason import ExitReason
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.theme import (
    BEAR_COLOR,
    BULL_COLOR,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.services.display_timezone_service import (
    DEFAULT_TIMEZONE,
    format_display_datetime,
)

#: Matches `BackTestPresenter`'s `_CUSTOM_TIME_FORMAT` — reused here instead
#: of the mockup's Vietnamese "16 thg 7, 2026" cosmetic format, which has no
#: existing formatter anywhere else in this codebase and would only ever be
#: used in this one column.
_DATETIME_FORMAT = "%Y-%m-%d %H:%M"

#: BOT-050 — `Trade.side` now exists; label reads it instead of assuming
#: every trade is a long ("vị thế mua"/"vị thế bán").
_POSITION_LABEL: dict[PositionSide, str] = {
    PositionSide.LONG: "vị thế mua",
    PositionSide.SHORT: "vị thế bán",
}

#: `STOP_LOSS`/`TAKE_PROFIT`/`LIQUIDATION` are declared but unreachable until
#: `BOT-041`/`BOT-049` — kept here anyway so the table never crashes on an
#: unrecognized `ExitReason` once they start showing up.
_EXIT_REASON_LABELS: dict[ExitReason, str] = {
    ExitReason.STRATEGY_SIGNAL: "Tín hiệu chiến lược",
    ExitReason.END_OF_BACKTEST: "Kết thúc backtest",
    ExitReason.STOP_LOSS: "Chạm Stop Loss (SL)",
    ExitReason.TAKE_PROFIT: "Chạm Take Profit (TP)",
    ExitReason.LIQUIDATION: "Thanh lý (Liquidation)",
}


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
    #: `BOT-045` Trade Journal Detail fields — power the table's expand row.
    entry_reason: str = ""
    exit_reason: ExitReason = ExitReason.STRATEGY_SIGNAL
    metadata: Mapping[str, Any] = field(default_factory=dict)
    #: BOT-050 — LONG for every row before this field existed.
    side: PositionSide = PositionSide.LONG


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
            entry_reason=trade.entry_reason,
            exit_reason=trade.exit_reason,
            metadata=trade.metadata,
            side=trade.side,
        )
        for position, trade in enumerate(trades, start=1)
    ]


def _format_duration(entry_time: datetime, exit_time: datetime) -> str:
    """@brief "4h 00m" style duration — not stored on `Trade` (BOT-045
    decision: derivable data shouldn't be duplicated), always computed here
    from `exit_time - entry_time`."""
    total_minutes = max(0, int((exit_time - entry_time).total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes:02d}m"


def _format_metadata_items(metadata: Mapping[str, Any]) -> list[dict[str, str]]:
    """@brief Renders whatever keys a strategy attached, in insertion order
    — no hardcoded "QML Score" or any other fixed schema (`BOT-045`: "tùy
    vào chiến thuật")."""
    return [
        {"label": key.replace("_", " ").title(), "value": str(value)}
        for key, value in metadata.items()
    ]


def _format_datetime(value: datetime, tz_name: str = DEFAULT_TIMEZONE) -> str:
    return format_display_datetime(value, tz_name=tz_name, fmt=_DATETIME_FORMAT)


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


def trade_log_row_to_qml(
    row: TradeLogRow, tz_name: str = DEFAULT_TIMEZONE
) -> dict[str, Any]:
    """Converts to the plain-dict shape QML's `Repeater`/`ListView` model
    expects (camelCase keys, everything pre-formatted as display text —
    same boundary convention as `stat_cards_to_qml`). `metadataItems` is the
    one non-string value — a list of `{label, value}` dicts for the expand
    row's `Repeater` (`BOT-045`), since metadata has no fixed set of keys."""
    pnl_color = BULL_COLOR if row.pnl >= 0 else BEAR_COLOR
    position_value = row.quantity * row.entry_price
    price_diff = row.exit_price - row.entry_price
    price_diff_color = BULL_COLOR if price_diff >= 0 else BEAR_COLOR
    price_diff_icon = "▲" if price_diff >= 0 else "▼"
    price_diff_icon_source = (
        "image://icons/triangle-up/success"
        if price_diff >= 0
        else "image://icons/triangle-down/danger"
    )
    return {
        "index": str(row.index),
        "positionLabel": f"#{row.index} {_POSITION_LABEL[row.side]}",
        "entryTimeText": _format_datetime(row.entry_time, tz_name=tz_name),
        "exitTimeText": _format_datetime(row.exit_time, tz_name=tz_name),
        "entryPriceText": f"{row.entry_price:,.2f} USD",
        "exitPriceText": f"{row.exit_price:,.2f} USD",
        "priceDiffText": _signed_pnl(price_diff, " USD"),
        "priceDiffColor": price_diff_color,
        "priceDiffIcon": price_diff_icon,
        "priceDiffIconSource": price_diff_icon_source,
        "positionSizeText": _format_compact_usd(position_value),
        "quantityText": f"{row.quantity:,.4g}",
        "pnlText": _signed_pnl(row.pnl, " USD"),
        "pnlColor": pnl_color,
        "returnText": _signed_pnl(row.pnl_percent, "%"),
        "entryReasonText": row.entry_reason or "—",
        "exitReasonText": _EXIT_REASON_LABELS[row.exit_reason],
        "durationText": _format_duration(row.entry_time, row.exit_time),
        "metadataItems": _format_metadata_items(row.metadata),
    }


def trade_log_rows_to_qml(
    rows: list[TradeLogRow], tz_name: str = DEFAULT_TIMEZONE
) -> list[dict[str, Any]]:
    return [trade_log_row_to_qml(row, tz_name=tz_name) for row in rows]
