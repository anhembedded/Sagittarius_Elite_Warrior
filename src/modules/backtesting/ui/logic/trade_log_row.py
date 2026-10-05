"""One finished trade, as the Trade Logs table shows it.

@par Where this lived before, and why it moved
`EPIC-015` put this file inside `qml/TradeLogTable/`, the package holding a QML
rendering of this table. `EPIC-025` PR 4.3h deleted that package: measured,
nothing in `src/` ever loaded its `.qml` — the screen has always rendered these
rows through the QtWidgets `BackTestTradeLogsPanel`, and the only thing that
built the QML one was its own `preview.py`. That is `CS-002`'s shape one level
out, and PR 4.3c had already found it once, in `DateRangeOverlay`.

What that package held that was **not** dead is this file and
`trade_log_filter.py`: the pure shaping and filtering the live panel imports.
They are `screens/backtest/logic/`'s now.

@par Raw values since `EPIC-033L`
The table was a hand-built list of rows, each a dict of pre-formatted text
(`trade_log_row_to_qml`, named for the QML it once fed), twenty to a page.
It is a `QTableView` over these rows now: the formatter writes each value by
its column's kind, a header click sorts, and the view scrolls instead of
paging. What a row could expand to show is `trade_details()`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

#: `STOP_LOSS`/`TAKE_PROFIT`/`LIQUIDATION` are declared but unreachable until
#: `BOT-041`/`BOT-049` — kept here anyway so the table never crashes on an
#: unrecognized `ExitReason` once they start showing up.
_EXIT_REASON_LABELS = EnumLabels(
    ExitReason,
    {
        ExitReason.STRATEGY_SIGNAL: "Strategy signal",
        ExitReason.END_OF_BACKTEST: "End of backtest",
        ExitReason.STOP_LOSS: "Hit Stop Loss (SL)",
        ExitReason.TAKE_PROFIT: "Hit Take Profit (TP)",
        ExitReason.LIQUIDATION: "Liquidation",
        ExitReason.PARTIAL_TAKE_PROFIT: "Partial Take Profit (scale-out)",
    },
)


@dataclass(frozen=True)
class TradeLogRow:
    """
    @brief One finished trade, as the Trades table holds it: raw values,
    written by the application's formatter by each column's kind
    (`trade_table_model.py`, `EPIC-033L`).

    @details `index` is the trade's 1-based position in the FULL,
    unfiltered `BacktestResult.trades` list — stable identity across
    filter, search and sorting, so "lệnh #12" always refers to the same trade
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
    #: BOT-106D — straight from `Trade.mae_percent`/`.mfe_percent`
    #: (BOT-106B). `0.0` means "no excursion observed" (the trade's own
    #: convention, e.g. entry and exit on the same bar), not "missing".
    mae_percent: float = 0.0
    mfe_percent: float = 0.0


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
            mae_percent=trade.mae_percent,
            mfe_percent=trade.mfe_percent,
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


def _signed_percent(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:,.2f}%"


def _metadata_label(key: str) -> str:
    """A strategy's metadata key as a reader sees it: no fixed schema, the
    keys are whatever the strategy attached (`BOT-045`: "tùy vào chiến
    thuật")."""
    return key.replace("_", " ").title()


def trade_details(row: TradeLogRow) -> tuple[tuple[str, str], ...]:
    """@brief The selected trade's journal (`BOT-045`): why it opened and
    closed, how long it ran, its worst and best excursion, then whatever
    the strategy attached, in insertion order.

    @details The Trades table holds the figures; these are the words the
    table has no column for. Before `EPIC-033L` they were each row's
    expandable section; now one read-out under the table shows them for
    the selected trade."""
    lines = [
        ("Entry reason", row.entry_reason or "—"),
        ("Exit reason", _EXIT_REASON_LABELS[row.exit_reason]),
        ("Duration", _format_duration(row.entry_time, row.exit_time)),
        ("Worst excursion (MAE)", _signed_percent(row.mae_percent)),
        ("Best excursion (MFE)", _signed_percent(row.mfe_percent)),
    ]
    lines += [(_metadata_label(key), str(value)) for key, value in row.metadata.items()]
    return tuple(lines)
