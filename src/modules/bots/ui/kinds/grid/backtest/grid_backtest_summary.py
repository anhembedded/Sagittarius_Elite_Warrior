"""`EPIC-029D` — a Grid backtest result in the words and numbers the page shows.

Pure functions, so what the user reads is tested without a widget:
· `summary_rows` — the figures beside the charts, each with its caveat: grid
  profit apart from unrealised, both curves' end value against the capital,
  fees by maker and taker, why the replay stopped, the fill rule, how many
  candles were replayed without 1-second klines (never silently, D14), and
  how many of the period's candles were stored;
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

_CENT = Decimal("0.01")
_STOP_WORDS = {
    StopReason.END_OF_DATA: "the last candle (no exit was reached)",
    StopReason.STOP_LOSS: "the stop loss: everything was sold at market",
    StopReason.TAKE_PROFIT: "the take profit: everything was sold at market",
    StopReason.HALTED: "a halt, as the live bot would have halted",
}


@dataclass(frozen=True, slots=True)
class SummaryRow:
    label: str
    value: str


def summary_rows(result: GridBacktestResult) -> tuple[SummaryRow, ...]:
    """@brief Every figure the page shows, in display order."""
    capital = _params(result).capital_quote
    end = result.equity[-1]
    provenance = result.provenance
    stop = _STOP_WORDS[result.stop_reason]
    if result.stop_detail:
        stop = f"{stop} ({result.stop_detail})"
    return (
        SummaryRow(
            "Period",
            f"{provenance.first_candle:%Y-%m-%d %H:%M} to "
            f"{provenance.last_candle:%Y-%m-%d %H:%M} UTC, {len(result.bars)} candles",
        ),
        SummaryRow("Grid at the end", _against(end.grid, capital)),
        SummaryRow("Buy and hold at the end", _against(end.buy_and_hold, capital)),
        SummaryRow(
            "Grid profit",
            f"{_money(result.grid_profit)} from {result.completed_cycles} closed cycles",
        ),
        SummaryRow("Unrealised", _money(result.unrealised)),
        SummaryRow(
            "Fees",
            f"{_money(result.maker_fees)} maker, {_money(result.taker_fees)} taker "
            f"({provenance.maker_fee:%} / {provenance.taker_fee:%})",
        ),
        SummaryRow("Stopped by", stop),
        SummaryRow("Fill rule", provenance.fill_rule),
        SummaryRow("Without 1-second klines", _coarse(result)),
        *_stored(result),
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


def _money(amount: Decimal) -> str:
    return f"{amount.quantize(_CENT):,} USDT"


def _against(value: Decimal, capital: Decimal) -> str:
    change = (value - capital) / capital * 100
    return f"{_money(value)} ({change.quantize(_CENT):+}%)"


def _coarse(result: GridBacktestResult) -> str:
    count = len(result.coarse_periods)
    if count == 0:
        return "none: every candle that could fill was replayed second by second"
    return (
        f"{count} of {len(result.bars)} candles: their order inside the candle "
        "was assumed (down first), which can understate a grid's cycles"
    )


def _stored(result: GridBacktestResult) -> tuple[SummaryRow, ...]:
    """How much of the period asked for was stored, when it is known."""
    window = result.provenance.window
    if window is None:
        return ()
    asked = f"{window.start:%Y-%m-%d %H:%M} to {window.end:%Y-%m-%d %H:%M} UTC"
    text = f"{window.stored_candles} of {window.expected_candles} in {asked}"
    if window.missing_candles:
        text += ": the replay ran on what is stored, not the whole period"
    return (SummaryRow("Candles stored", text),)
