"""`EPIC-039K` — what the price can reach on one leg of a step, and what each thing does.

@details On a falling leg a long can be liquidated, the stop loss below the range can be reached
and a resting BUY can fill; on a rising leg the mirror: a short, the take profit, a SELL. Each
has the price it happens at (`trigger`); the replay takes the first the price reaches (the
highest on a fall, the lowest on a rise). The list is built liquidation, exit, fill and the
replay keeps the first of equals, so at one price the exchange liquidates before a stop order
could fill. The consequences are the replay's (`LegActions`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_ladder import Ladder
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    PriceStep,
)


@dataclass(frozen=True, slots=True)
class LegEvent:
    """Something the price reaches on a leg: the price it happens at, and what it does."""

    trigger: Decimal
    run: Callable[[], None]


@dataclass(frozen=True, slots=True)
class LegSituation:
    """What the replay knows when it asks what the leg reaches."""

    step: PriceStep
    falling: bool
    #: The liquidation price of the position held, `None` when no price liquidates it.
    liquidation_limit: Decimal | None
    position: Decimal
    stop_loss: Decimal | None
    take_profit: Decimal | None
    tick: Decimal


@dataclass(frozen=True, slots=True)
class LegActions:
    """What reaching each thing does: the replay's own books."""

    liquidate: Callable[[Decimal, datetime], None]
    exit: Callable[[StopReason, Decimal, datetime], None]
    fill: Callable[[int, datetime], None]


def leg_events(
    situation: LegSituation, ladder: Ladder, actions: LegActions
) -> list[LegEvent]:
    """The things the leg reaches from here, liquidation first."""
    candidates = [
        _liquidation(situation, actions),
        _exit(situation, actions),
        _fill(situation, ladder, actions),
    ]
    return [event for event in candidates if event is not None]


def _liquidation(situation: LegSituation, actions: LegActions) -> LegEvent | None:
    limit, step = situation.liquidation_limit, situation.step
    if limit is None:
        return None
    if situation.falling:
        reached = situation.position > 0 and step.low <= limit
    else:
        reached = situation.position < 0 and step.high >= limit
    if not reached:
        return None
    return LegEvent(limit, lambda: actions.liquidate(limit, step.time))


def _exit(situation: LegSituation, actions: LegActions) -> LegEvent | None:
    step = situation.step
    if situation.falling:
        stop = situation.stop_loss
        if stop is None or step.low > stop:
            return None
        price = min(stop, step.open)
        return LegEvent(
            stop, lambda: actions.exit(StopReason.STOP_LOSS, price, step.time)
        )
    take = situation.take_profit
    if take is None or step.high < take:
        return None
    price = max(take, step.open)
    return LegEvent(
        take, lambda: actions.exit(StopReason.TAKE_PROFIT, price, step.time)
    )


def _fill(
    situation: LegSituation, ladder: Ladder, actions: LegActions
) -> LegEvent | None:
    step = situation.step
    if situation.falling:
        index = ladder.next_buy(step.low)
        offset = -situation.tick
    else:
        index = ladder.next_sell(step.high)
        offset = situation.tick
    if index is None:
        return None
    return LegEvent(
        ladder.price_of(index) + offset, lambda: actions.fill(index, step.time)
    )
