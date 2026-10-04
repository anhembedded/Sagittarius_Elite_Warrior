"""`EPIC-029D` — when a resting Grid order counts as filled in a replay (ADR D14).

A backtest has candles, not the order book, so it needs a rule for what a
candle proves. This one is deliberately strict, because a simulator that fills
too generously gives false confidence (the task's main risk):

· **No fill on touch.** A BUY at L fills only when the price traded at least
  one tick through it (`low ≤ L − tick`); a SELL only when `high ≥ L + tick`.
  Touching L proves nothing about the queue ahead of the order.
· **The order inside a candle** comes from its 1-second klines: each one is a
  `PriceStep`, visited open → low → high → close when it closed up and
  open → high → low → close when it closed down.
· **At most one fill per level per step**, and an order placed during a step
  (a counter order) rests from the next one, so one 1-second kline never
  completes a round trip.
· **Without 1-second klines** a candle is one coarse step visited adverse side
  first, down then up, so the levels the grid buys fill before any it sells;
  the replay marks the candle in `coarse_periods`, never silently.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

#: How every result names this rule (the result view shows it).
FILL_RULE = (
    "BUY at L fills when low <= L - tick, SELL when high >= L + tick; "
    "order within a candle from 1-second klines (down then up without them); "
    "one fill per level per 1-second kline; counter orders rest from the next one"
)


@dataclass(frozen=True, slots=True)
class PriceBar:
    """One candle, in the bots module's own terms."""

    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    def __post_init__(self) -> None:
        if (
            not self.low
            <= min(self.open, self.close)
            <= max(self.open, self.close)
            <= self.high
        ):
            raise ValueError(f"candle at {self.time} is not low <= open/close <= high")


class Leg(str, Enum):
    """One direction the price travels inside a step."""

    DOWN = "DOWN"
    UP = "UP"


@dataclass(frozen=True, slots=True)
class PriceStep:
    """The unit the replay fills in: the range traded and the order it went."""

    time: datetime
    open: Decimal
    low: Decimal
    high: Decimal
    legs: tuple[Leg, Leg]
    coarse: bool = False


def buy_fills(level_price: Decimal, low: Decimal, tick: Decimal) -> bool:
    """A resting BUY at `level_price` filled when the price traded a tick below."""
    return low <= level_price - tick


def sell_fills(level_price: Decimal, high: Decimal, tick: Decimal) -> bool:
    """A resting SELL at `level_price` filled when the price traded a tick above."""
    return high >= level_price + tick


def steps_for(bar: PriceBar, fine: Sequence[PriceBar]) -> tuple[PriceStep, ...]:
    """The steps one candle is replayed as: its 1-second klines, or itself."""
    if not fine:
        return (PriceStep(bar.time, bar.open, bar.low, bar.high, _ADVERSE, True),)
    return tuple(_fine_step(kline) for kline in fine)


_ADVERSE = (Leg.DOWN, Leg.UP)


def _fine_step(kline: PriceBar) -> PriceStep:
    legs = (Leg.DOWN, Leg.UP) if kline.close >= kline.open else (Leg.UP, Leg.DOWN)
    return PriceStep(kline.time, kline.open, kline.low, kline.high, legs)
