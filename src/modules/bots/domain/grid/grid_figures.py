"""`EPIC-040B` — a Grid replay's figures and caveats, as the kind-neutral outcome carries them.

Pure functions: the figures beside the charts and their caveats (`EPIC-029D`), written once, in the
outcome `GridKindBacktester` answers with, which the workbench draws (the Grid's own page, which
drew them too, is gone, `EPIC-040F`):
· `grid_figures` — grid profit apart from unrealised, both curves' end value against the capital,
  fees by maker and taker, how many candles were replayed without 1-second klines (never silently,
  D14) and how many of the period's were stored; a position venue adds funding, the margin a
  liquidation took and how near the price came to one (`EPIC-039K`). Values are raw; the
  application's formatter writes them (`EPIC-033N`);
· `grid_notes` — why the replay stopped, the fill rule and what the coarse or missing candles
  mean, as sentences, the missing funding first.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestFigure,
    FigureKind,
    FigureValue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestResult,
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)

_STOP_WORDS = {
    StopReason.END_OF_DATA: "the last candle (no exit was reached)",
    StopReason.STOP_LOSS: "the stop loss: everything was sold at market",
    StopReason.TAKE_PROFIT: "the take profit: everything was sold at market",
    StopReason.HALTED: "a halt, as the live bot would have halted",
    StopReason.LIQUIDATED: (
        "a liquidation: the exchange closes the position and the margin is lost"
    ),
}
_HUNDRED = Decimal(100)


def grid_figures(result: GridBacktestResult) -> tuple[BacktestFigure, ...]:
    """@brief Every figure the page shows, in display order; a figure that does not exist (no
    liquidation price applied, no period asked for) is not in the list."""
    capital = GridParams.from_config(dict(result.provenance.config)).capital_quote
    end = result.equity[-1]
    provenance = result.provenance
    figures = [
        _figure(
            "first_candle",
            "First candle",
            FigureKind.TIMESTAMP,
            provenance.first_candle,
        ),
        _figure(
            "last_candle", "Last candle", FigureKind.TIMESTAMP, provenance.last_candle
        ),
        _figure("candles", "Candles replayed", FigureKind.QUANTITY, len(result.bars)),
        _figure("grid_end", "Grid at the end (USDT)", FigureKind.MONEY, end.grid),
        _figure(
            "grid_change",
            "Grid against the capital",
            FigureKind.PERCENT,
            _change(end.grid, capital),
        ),
        _figure(
            "hold_end",
            "Buy and hold at the end (USDT)",
            FigureKind.MONEY,
            end.buy_and_hold,
        ),
        _figure(
            "hold_change",
            "Buy and hold against the capital",
            FigureKind.PERCENT,
            _change(end.buy_and_hold, capital),
        ),
        _figure(
            "grid_profit", "Grid profit (USDT)", FigureKind.MONEY, result.grid_profit
        ),
        _figure(
            "cycles", "Closed cycles", FigureKind.QUANTITY, result.completed_cycles
        ),
        _figure("unrealised", "Unrealised (USDT)", FigureKind.MONEY, result.unrealised),
        _figure("maker_fees", "Maker fees (USDT)", FigureKind.MONEY, result.maker_fees),
        _figure(
            "maker_rate",
            "Maker fee rate",
            FigureKind.PERCENT,
            provenance.maker_fee * _HUNDRED,
        ),
        _figure("taker_fees", "Taker fees (USDT)", FigureKind.MONEY, result.taker_fees),
        _figure(
            "taker_rate",
            "Taker fee rate",
            FigureKind.PERCENT,
            provenance.taker_fee * _HUNDRED,
        ),
        _figure(
            "coarse_candles",
            "Candles without 1-second klines",
            FigureKind.QUANTITY,
            len(result.coarse_periods),
        ),
    ]
    figures += _futures_figures(result)
    figures += _stored_figures(result)
    return tuple(figures)


def grid_notes(result: GridBacktestResult) -> tuple[str, ...]:
    """@brief The caveats that qualify the figures: why the replay stopped, the fill rule,
    candles replayed without 1-second klines, a period not wholly stored."""
    stop = _STOP_WORDS[result.stop_reason]
    if result.stop_detail:
        stop = f"{stop} ({result.stop_detail})"
    notes = [f"Stopped by {stop}.", f"Fill rule: {result.provenance.fill_rule}"]
    notes[:0] = _range_wait_notes(result)
    notes[:0] = _futures_notes(result)
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


def _range_wait_notes(result: GridBacktestResult) -> list[str]:
    """`EPIC-044D`: a window that opened outside the range waited for it, as the live bot does."""
    if not result.waited_for_range:
        return []
    entry = result.range_entry
    if entry is None:
        return [
            (
                "The price was outside the range at the first candle and never entered it: "
                "the bot waited, placed nothing and the equity stayed the capital."
            )
        ]
    notes = [
        (
            "The price was outside the range at the first candle, so the bot waited and "
            f"entered at {entry.time:%Y-%m-%d %H:%M:%S} UTC, at {entry.price}: the first step "
            "that closed inside it. The buy-and-hold benchmark buys at the same step."
        )
    ]
    if result.futures is not None:
        notes.append(
            "A position venue has no mark-price history here, so the entry is judged on the "
            "trade close; a live bot judges it on the mark, which can differ."
        )
    return notes


def _figure(
    key: str, title: str, kind: FigureKind, value: FigureValue
) -> BacktestFigure:
    return BacktestFigure(key, title, kind, value)


def _futures_figures(result: GridBacktestResult) -> list[BacktestFigure]:
    """What a replay on a position venue adds (`EPIC-039K`): funding apart from the grid profit,
    the margin a liquidation took, and how near the price came to one."""
    futures = result.futures
    if futures is None:
        return []
    figures = [
        _figure(
            "funding_paid",
            "Funding paid (USDT, negative earned)",
            FigureKind.MONEY,
            futures.funding_paid,
        )
    ]
    if futures.closest_to_liquidation is not None:
        figures.append(
            _figure(
                "closest_to_liquidation",
                "Closest to liquidation (of the price)",
                FigureKind.PERCENT,
                futures.closest_to_liquidation * _HUNDRED,
            )
        )
    figures.append(
        _figure(
            "margin_lost",
            "Margin lost to a liquidation (USDT)",
            FigureKind.MONEY,
            futures.margin_lost,
        )
    )
    return figures


def _stored_figures(result: GridBacktestResult) -> list[BacktestFigure]:
    """How much of the period asked for was stored, when a period was asked."""
    window = result.provenance.window
    if window is None:
        return []
    return [
        _figure("asked_from", "Period asked from", FigureKind.TIMESTAMP, window.start),
        _figure("asked_to", "Period asked to", FigureKind.TIMESTAMP, window.end),
        _figure(
            "expected_candles",
            "Candles in the period",
            FigureKind.QUANTITY,
            window.expected_candles,
        ),
        _figure(
            "stored_candles",
            "Candles stored",
            FigureKind.QUANTITY,
            window.stored_candles,
        ),
    ]


def _change(value: Decimal, capital: Decimal) -> Decimal:
    """`value` against the capital, in percent."""
    return (value - capital) / capital * _HUNDRED


def _futures_notes(result: GridBacktestResult) -> list[str]:
    """What qualifies a position venue's figures, the missing funding first (`EPIC-039K`)."""
    futures = result.futures
    if futures is None:
        return []
    notes = [futures.funding_note]
    notes.append(
        "Modelled, not replayed: this is a model of a position grid with a Futures bot's "
        "costs, funding and liquidation. It has not been checked against a Futures bot's "
        "own fills yet, so treat it as an estimate."
    )
    if futures.leverage > 1 and futures.closest_to_liquidation is None:
        notes.append("No liquidation price applied to the positions held.")
    return notes
