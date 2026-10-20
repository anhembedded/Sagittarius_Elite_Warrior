"""`EPIC-040D` — a kind-neutral backtest outcome as the workbench draws it.

Pure functions and the fills table's model, so what a person reads is tested without a widget:
· `chart_candles` — the replayed candles as the chart draws them (no volume is replayed);
· `result_overlay` — the kind's own overlay for the parameters tried (`IBotKind.overlay`, which the
  planner and the running bot draw too, ADR D16) plus the replay's fills, each where and when it
  traded;
· `figure_readout` — the outcome's figures as a read-out of raw values by kind, which the
  application's formatter writes (`EPIC-033N`);
· `FillsTableModel` — the replay's fills, each as its kind labelled it.

A figure's `tone` is not drawn: no kind sets one yet and the read-out has no sanctioned way to paint a
value (`ui-presentation-rule.md` §1); the figure's sign and words carry its meaning.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import ClassVar

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_kind import IBotKind
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestFill,
    BacktestOutcome,
    FigureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.sandbox_plan import (
    SandboxPlan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    BotKindInputs,
    ExchangeTerms,
    MarketView,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import (
    BotOverlay,
    FillSide,
    OverlayFill,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import Readout
from Sagittarius_Elite_Warrior.src.support.ui_kit.table_model import RowTableModel
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
    DisplayValue,
)

#: How the neutral figure kinds are written and aligned by the engine's read-out.
_COLUMN_KINDS = {
    FigureKind.TIMESTAMP: ColumnKind.TIMESTAMP,
    FigureKind.QUANTITY: ColumnKind.QUANTITY,
    FigureKind.MONEY: ColumnKind.MONEY,
    FigureKind.PERCENT: ColumnKind.PERCENT,
}


def chart_candles(
    outcome: BacktestOutcome, symbol: str, interval: TimeFrame
) -> list[MarketData]:
    """The replayed candles as the chart draws them (no volume is replayed)."""
    length = timedelta(seconds=interval.to_seconds())
    return [
        MarketData(
            symbol=symbol,
            interval=interval.value,
            open_time=bar.time,
            open_price=float(bar.open),
            high_price=float(bar.high),
            low_price=float(bar.low),
            close_price=float(bar.close),
            volume=0.0,
            close_time=bar.time + length,
            quote_asset_volume=0.0,
            number_of_trades=0,
            taker_buy_base_asset_volume=0.0,
            taker_buy_quote_asset_volume=0.0,
        )
        for bar in outcome.bars
    ]


def result_overlay(
    kind: IBotKind,
    plan: SandboxPlan,
    terms: ExchangeTerms,
    outcome: BacktestOutcome,
) -> BotOverlay:
    """The kind's overlay for the parameters tried, drawn at the replay's first price, with the
    replay's fills on top."""
    first = outcome.bars[0].open if outcome.bars else None
    overlay = BotOverlay()
    if first is not None:
        overlay = kind.overlay(BotKindInputs(plan.config, terms, MarketView(first)))
    return replace(
        overlay,
        fills=tuple(
            OverlayFill(
                fill.time,
                fill.price,
                FillSide.BUY if fill.side is OrderSide.BUY else FillSide.SELL,
                fill.label,
            )
            for fill in outcome.fills
        ),
    )


def figure_readout(outcome: BacktestOutcome) -> Readout:
    """Every figure of the outcome, in its order, as a read-out of raw values by kind."""
    values: dict[str, DisplayValue] = {}
    specs = []
    for figure in outcome.figures:
        specs.append(ColumnSpec(figure.key, figure.title, _COLUMN_KINDS[figure.kind]))
        values[figure.key] = figure.value
    return Readout(tuple(specs), values)


class FillsTableModel(RowTableModel[BacktestFill]):
    """The replay's fills, oldest first, each as its kind labelled it."""

    COLUMNS: ClassVar[tuple[ColumnSpec, ...]] = (
        ColumnSpec("time", "Time", ColumnKind.TIMESTAMP),
        ColumnSpec("label", "Fill", ColumnKind.TEXT),
        ColumnSpec("side", "Side", ColumnKind.SIDE),
        ColumnSpec("price", "Price", ColumnKind.PRICE),
        ColumnSpec("quantity", "Quantity", ColumnKind.QUANTITY),
        ColumnSpec("fee", "Fee", ColumnKind.MONEY),
        ColumnSpec("kind", "Order", ColumnKind.TEXT),
    )

    def _value(self, row: BacktestFill, column: int) -> DisplayValue:
        values: tuple[DisplayValue, ...] = (
            row.time,
            row.label,
            row.side.value.capitalize(),
            row.price,
            row.quantity,
            row.fee_quote,
            "Resting" if row.maker else "Market",
        )
        return values[column]


def missing_candles(outcome: BacktestOutcome | None) -> int:
    """How many candles of the period the replay found not stored (`0` for none, or no outcome)."""
    window = outcome.provenance.window if outcome is not None else None
    return window.missing_candles if window is not None else 0
