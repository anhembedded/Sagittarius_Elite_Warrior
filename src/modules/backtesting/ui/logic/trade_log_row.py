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
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.exit_reason import (
    ExitReason,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.trade import Trade
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import Readout
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

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


#: The journal's fixed rows (`BOT-045`): the words and figures the Trades
#: table has no column for. A strategy's metadata follows them.
_JOURNAL_SPECS = (
    ColumnSpec("entry_reason", "Entry reason", ColumnKind.TEXT),
    ColumnSpec("exit_reason", "Exit reason", ColumnKind.TEXT),
    ColumnSpec("duration", "Duration", ColumnKind.DURATION),
    ColumnSpec("mae", "Worst excursion (MAE)", ColumnKind.PERCENT),
    ColumnSpec("mfe", "Best excursion (MFE)", ColumnKind.PERCENT),
)
#: A metadata row's key, kept apart from the fixed rows' whatever the
#: strategy names its own.
_METADATA_KEY = "metadata:{}"


def _metadata_spec(key: str, value: object) -> ColumnSpec:
    """A strategy's metadata key as a reader sees it: no fixed schema, the
    keys are whatever the strategy attached (`BOT-045`: "tùy vào chiến
    thuật"). A number is a figure; anything else is words. An ampersand in
    the key is text, never an access key."""
    title = key.replace("_", " ").title().replace("&", "&&")
    kind = ColumnKind.QUANTITY if _is_figure(value) else ColumnKind.TEXT
    return ColumnSpec(_METADATA_KEY.format(key), title, kind)


def _is_figure(value: object) -> bool:
    return isinstance(value, int | float | Decimal) and not isinstance(value, bool)


def _metadata_value(value: object) -> DisplayValue:
    if isinstance(value, int | float | Decimal) and _is_figure(value):
        return value
    return str(value)


def trade_details(row: TradeLogRow) -> Readout:
    """@brief The selected trade's journal (`BOT-045`): why it opened and
    closed, how long it ran, its worst and best excursion, then whatever
    the strategy attached, in insertion order.

    @details The Trades table holds the figures; these are the words the
    table has no column for. Before `EPIC-033L` they were each row's
    expandable section; now one read-out under the table shows them for
    the selected trade. Each is a raw value of its row's kind, written by
    the application's formatter (`EPIC-033N`): the duration is a
    `timedelta` (never negative: `Trade` does not store it, it is derived
    here), an excursion a percent, a blank entry reason an empty value."""
    values: dict[str, DisplayValue] = {
        "entry_reason": row.entry_reason or None,
        "exit_reason": _EXIT_REASON_LABELS[row.exit_reason],
        "duration": max(row.exit_time - row.entry_time, timedelta(0)),
        "mae": row.mae_percent,
        "mfe": row.mfe_percent,
    }
    specs = list(_JOURNAL_SPECS)
    for key, value in row.metadata.items():
        spec = _metadata_spec(key, value)
        specs.append(spec)
        values[spec.key] = _metadata_value(value)
    return Readout(tuple(specs), values)
