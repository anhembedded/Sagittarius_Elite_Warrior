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
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import BotOverlay
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestResult,
    StopReason,
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
    DisplayValue,
)

_STOP_WORDS = {
    StopReason.END_OF_DATA: "the last candle (no exit was reached)",
    StopReason.STOP_LOSS: "the stop loss: everything was sold at market",
    StopReason.TAKE_PROFIT: "the take profit: everything was sold at market",
    StopReason.HALTED: "a halt, as the live bot would have halted",
}
_HUNDRED = Decimal(100)

#: The figures every replay has, top to bottom. Units are in the titles;
#: each value is written by the application's formatter (`EPIC-033N`).
_FIGURES = (
    ColumnSpec("first_candle", "First candle", ColumnKind.TIMESTAMP),
    ColumnSpec("last_candle", "Last candle", ColumnKind.TIMESTAMP),
    ColumnSpec("candles", "Candles replayed", ColumnKind.QUANTITY),
    ColumnSpec("grid_end", "Grid at the end (USDT)", ColumnKind.MONEY),
    ColumnSpec("grid_change", "Grid against the capital", ColumnKind.PERCENT),
    ColumnSpec("hold_end", "Buy and hold at the end (USDT)", ColumnKind.MONEY),
    ColumnSpec("hold_change", "Buy and hold against the capital", ColumnKind.PERCENT),
    ColumnSpec("grid_profit", "Grid profit (USDT)", ColumnKind.MONEY),
    ColumnSpec("cycles", "Closed cycles", ColumnKind.QUANTITY),
    ColumnSpec("unrealised", "Unrealised (USDT)", ColumnKind.MONEY),
    ColumnSpec("maker_fees", "Maker fees (USDT)", ColumnKind.MONEY),
    ColumnSpec("maker_rate", "Maker fee rate", ColumnKind.PERCENT),
    ColumnSpec("taker_fees", "Taker fees (USDT)", ColumnKind.MONEY),
    ColumnSpec("taker_rate", "Taker fee rate", ColumnKind.PERCENT),
    ColumnSpec(
        "coarse_candles", "Candles without 1-second klines", ColumnKind.QUANTITY
    ),
)
#: How much of the period asked for was stored, when a period was asked.
_STORED = (
    ColumnSpec("asked_from", "Period asked from", ColumnKind.TIMESTAMP),
    ColumnSpec("asked_to", "Period asked to", ColumnKind.TIMESTAMP),
    ColumnSpec("expected_candles", "Candles in the period", ColumnKind.QUANTITY),
    ColumnSpec("stored_candles", "Candles stored", ColumnKind.QUANTITY),
)


@dataclass(frozen=True, slots=True)
class GridSummary:
    """A replay's figures as a read-out, and its caveats in words."""

    readout: Readout
    notes: tuple[str, ...]


def summary_of(result: GridBacktestResult) -> GridSummary:
    """@brief Every figure the page shows, in display order, and the caveats
    that qualify them (why the replay stopped, the fill rule, candles
    replayed without 1-second klines, a period not wholly stored)."""
    return GridSummary(
        Readout(_FIGURES + _stored_specs(result), _values(result)),
        _notes(result),
    )


def _values(result: GridBacktestResult) -> dict[str, DisplayValue]:
    capital = _params(result).capital_quote
    end = result.equity[-1]
    provenance = result.provenance
    values: dict[str, DisplayValue] = {
        "first_candle": provenance.first_candle,
        "last_candle": provenance.last_candle,
        "candles": len(result.bars),
        "grid_end": end.grid,
        "grid_change": _change(end.grid, capital),
        "hold_end": end.buy_and_hold,
        "hold_change": _change(end.buy_and_hold, capital),
        "grid_profit": result.grid_profit,
        "cycles": result.completed_cycles,
        "unrealised": result.unrealised,
        "maker_fees": result.maker_fees,
        "maker_rate": provenance.maker_fee * _HUNDRED,
        "taker_fees": result.taker_fees,
        "taker_rate": provenance.taker_fee * _HUNDRED,
        "coarse_candles": len(result.coarse_periods),
    }
    window = provenance.window
    if window is not None:
        values |= {
            "asked_from": window.start,
            "asked_to": window.end,
            "expected_candles": window.expected_candles,
            "stored_candles": window.stored_candles,
        }
    return values


def _stored_specs(result: GridBacktestResult) -> tuple[ColumnSpec, ...]:
    return () if result.provenance.window is None else _STORED


def _change(value: Decimal, capital: Decimal) -> Decimal:
    """`value` against the capital, in percent."""
    return (value - capital) / capital * _HUNDRED


def _notes(result: GridBacktestResult) -> tuple[str, ...]:
    stop = _STOP_WORDS[result.stop_reason]
    if result.stop_detail:
        stop = f"{stop} ({result.stop_detail})"
    notes = [f"Stopped by {stop}.", f"Fill rule: {result.provenance.fill_rule}"]
    if result.coarse_periods:
        notes.append(
            "Without 1-second klines the order of prices inside a candle was "
            "assumed (down first), which can understate a grid's cycles."
        )
    else:
        notes.append("Every candle that could fill was replayed second by second.")
    window = result.provenance.window
    if window is not None and window.missing_candles:
        notes.append("The replay ran on what is stored, not the whole period.")
    return tuple(notes)


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
