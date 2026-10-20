"""`EPIC-029D` — a Grid backtest result in the words and numbers the page shows.

Pure functions, so what the user reads is tested without a widget:
· `summary_of` — the figures beside the charts and their caveats: grid
  profit apart from unrealised, both curves' end value against the capital,
  fees by maker and taker, how many candles were replayed without 1-second
  klines (never silently, D14) and how many of the period's were stored, as
  a read-out of raw values by kind that the application's formatter writes
  (`EPIC-033N`); why the replay stopped, the fill rule and what the coarse
  or missing candles mean, as sentences;
· `chart_candles` — the replayed candles as the chart draws them;
· `result_overlay` — the plan with the replay's fills and final level
  states, through `grid_overlay`, the one computation the planner and the
  running bot also draw (ADR D16).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    FigureKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_figures import (
    grid_figures,
    grid_notes,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    GridOverlaySource,
    grid_overlay,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.readout_slot import Readout
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    ColumnSpec,
)

#: How the neutral figure kinds are written and aligned by the engine's read-out.
_COLUMN_KINDS = {
    FigureKind.TIMESTAMP: ColumnKind.TIMESTAMP,
    FigureKind.QUANTITY: ColumnKind.QUANTITY,
    FigureKind.MONEY: ColumnKind.MONEY,
    FigureKind.PERCENT: ColumnKind.PERCENT,
}


@dataclass(frozen=True, slots=True)
class GridSummary:
    """A replay's figures as a read-out, and its caveats in words."""

    readout: Readout
    notes: tuple[str, ...]


def summary_of(result: GridBacktestResult) -> GridSummary:
    """@brief Every figure the page shows, in display order, and the caveats that qualify
    them (`grid_figures`, `grid_notes`: the same the kind-neutral outcome carries)."""
    figures = grid_figures(result)
    return GridSummary(
        Readout(
            tuple(
                ColumnSpec(figure.key, figure.title, _COLUMN_KINDS[figure.kind])
                for figure in figures
            ),
            {figure.key: figure.value for figure in figures},
        ),
        grid_notes(result),
    )


def chart_candles(
    result: GridBacktestResult, symbol: str, interval: TimeFrame
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
        for bar in result.bars
    ]


def result_overlay(result: GridBacktestResult) -> BotOverlay:
    """The plan, the replay's fills and its final level states."""
    return grid_overlay(
        GridOverlaySource(
            params=_params(result),
            plan=result.plan,
            thresholds=GridThresholds(),
            activity=result.activity(),
        )
    )


def _params(result: GridBacktestResult) -> GridParams:
    return GridParams.from_config(dict(result.provenance.config))
