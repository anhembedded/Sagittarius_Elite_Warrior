"""`BOT-193` — a Grid bot's ladder, its summary and where the price stands, from the saved record.

The Bots tab (`ui/bots_screen/bot_ladder_panel.py`) and `bot show` show the same figures, so both
build them here from the bot's record (`BotSnapshot`): no exchange call, no host, no lock, and no
Qt, because a headless host installs none. The wording is `grid_ladder_texts.py`.

Every figure says what it is (`PRO-016` section 2):
  · **designed** — from the parameters the bot is given, read now (the saved ones for `bot show`;
    the design on screen for the Bots tab, which says when it is not saved): the levels, the step
    between neighbours and the net after fees. A bot edited with `bot edit` shows the edited
    ladder, never a cached one. The prices are the raw levels (`grid_spacing.raw_levels`); the tick
    rounding needs the exchange's filters, which the record does not hold, so a row may differ from
    the resting order by less than one tick;
  · **recorded** — from the saved run: what each rung is doing, the last price the bot heard and
    when, and the profit its completed cycles booked;
  · **estimate** — the profit of one cycle in the quote asset, which depends on the quantity the
    bot sizes at start (exchange lot steps, the opening price), so it is the capital over the
    `grid_count` levels that hold an order (one of the `grid_count + 1` is empty at the price) and
    says so. (`plan` divides by `grid_count + 1` when the price is outside the range, so there
    the estimate is up to one level's share high.)

A figure that needs something the record does not hold is `None`, never zero: no price heard, no
fee rate (the account's maker rate is recorded when a run starts, so a file an earlier build wrote
has none, and the net after fees is `None` and the profit is shown before fees), no run.

Nothing here promises how often the price crosses a level, and there is no profit per day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from itertools import pairwise

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotOrderLine,
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
    venue_profile_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_derived import (
    GridProfit,
    grid_profits,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
    GridParamsError,
    GridSpacing,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_spacing import (
    raw_levels,
)

_ZERO = Decimal(0)
_HALF = Decimal("0.5")


class LadderState(str, Enum):
    """What a grid's two levels are doing, as the saved run records it."""

    WAITING_TO_BUY = "waiting to buy"
    WAITING_TO_SELL = "waiting to sell"
    #: The lower level holds a BUY and the upper a SELL: the price stands inside this grid.
    WAITING_BOTH = "waiting to buy and sell"
    NO_ORDER = "no order"
    #: There is no run to read, or it is not this ladder: nothing is claimed.
    NOT_RECORDED = "not recorded"


@dataclass(frozen=True, slots=True)
class LadderRow:
    """One grid: the buy level and the sell level above it."""

    buy: Decimal
    sell: Decimal
    #: Designed: `(sell − buy) / buy`.
    step_fraction: Decimal
    #: Designed: the step less both legs' maker fee; `None` while the fee rate is unknown.
    net_fraction: Decimal | None
    #: Estimate: one completed cycle's profit before fees, `None` when the sizing is unknown.
    gross_quote: Decimal | None
    #: Estimate: the same after both legs' fees; `None` while the fee rate is unknown.
    net_quote: Decimal | None
    #: Recorded.
    state: LadderState


@dataclass(frozen=True, slots=True)
class LadderSummary:
    """The ladder in one line (`grid_ladder_texts.summary_line`)."""

    spacing: GridSpacing
    smallest_step_fraction: Decimal
    largest_step_fraction: Decimal
    #: The account's maker rate both legs paid, or `None` when it is not known.
    maker_fee: Decimal | None
    #: Estimate: the average profit of one cycle, after fees when `maker_fee` is known and
    #: before them when it is not; `None` when the sizing is unknown.
    average_cycle_quote: Decimal | None


@dataclass(frozen=True, slots=True)
class RecordedCycles:
    """Recorded: what the completed cycles booked, net of both legs' fees (Futures funding is not in it)."""

    completed_cycles: int
    #: The profit the cycles booked; `None` when the record holds no run.
    grid_profit: Decimal | None

    @property
    def average_profit(self) -> Decimal | None:
        if self.grid_profit is None or self.completed_cycles <= 0:
            return None
        return self.grid_profit / self.completed_cycles


@dataclass(frozen=True, slots=True)
class PriceMark:
    """A price of the parameters and how far the bot's last price is from it (per cent of that price)."""

    price: Decimal
    #: `(price − last) / last`: negative below the last price; `None` without a last price.
    distance_fraction: Decimal | None


@dataclass(frozen=True, slots=True)
class PricePosition:
    """Recorded: where the last price the bot heard stands against the range and the exits."""

    #: `None` before the bot heard one.
    last_price: Decimal | None
    #: How long before `now` the bot heard it; `None` when the record holds no moment.
    age_seconds: int | None
    lower: PriceMark
    upper: PriceMark
    stop_loss: PriceMark | None
    take_profit: PriceMark | None
    #: A position venue has a liquidation price, which the exchange reports while the bot runs
    #: and the record does not hold.
    has_liquidation_price: bool


@dataclass(frozen=True, slots=True)
class GridLadder:
    rows: tuple[LadderRow, ...]
    summary: LadderSummary
    recorded: RecordedCycles
    position: PricePosition
    #: Why the rungs' states are not shown, empty when they are or when there is no run.
    run_note: str = ""


@dataclass(frozen=True, slots=True)
class LadderUnavailable:
    """No ladder to show, and why, in words for the person."""

    reason: str


NO_LADDER_FOR_KIND = "This kind of bot has no ladder."
RUN_DIFFERS_NOTE = (
    "The saved run's ladder is not the one these parameters make (they differ from the "
    "ones the run began with), so what each grid is doing is not shown."
)


def grid_ladder_of(bot: BotSnapshot, now: datetime) -> GridLadder | LadderUnavailable:
    """The ladder of `bot` as its saved record makes it.

    The maker rate is the one the run's start recorded (`BotProgress.maker_fee`, `BOT-194`), the
    only source a reader with no exchange has, and it is worded as such. With it the net after fees
    is filled in, without it (a run from before it was recorded) the profit is before fees.
    """
    if bot.kind != GRID_KIND_ID:
        return LadderUnavailable(NO_LADDER_FOR_KIND)
    try:
        params = GridParams.from_config(bot.config)
    except GridParamsError as exc:
        return LadderUnavailable(f"The parameters make no ladder yet: {exc}.")
    levels = raw_levels(params.lower, params.upper, params.grid_count, params.spacing)
    progress = bot.progress
    maker_fee = progress.maker_fee if progress is not None else None
    states, run_note = _states(levels, progress)
    gross = grid_profits(levels, _ZERO)
    net = grid_profits(levels, maker_fee) if maker_fee is not None else None
    notionals = _notionals(bot, params, levels)
    rows = tuple(
        _row(
            grid,
            net[index] if net is not None else None,
            notionals[index],
            states[index],
        )
        for index, grid in enumerate(gross)
    )
    return GridLadder(
        rows=rows,
        summary=_summary(params, rows, maker_fee),
        recorded=RecordedCycles(
            progress.completed_cycles if progress else 0,
            progress.realised_profit if progress else None,
        ),
        position=_position(params, bot, now),
        run_note=run_note,
    )


def _row(
    grid: GridProfit,
    net: GridProfit | None,
    notional: Decimal | None,
    state: LadderState,
) -> LadderRow:
    return LadderRow(
        buy=grid.buy,
        sell=grid.sell,
        step_fraction=grid.step_fraction,
        net_fraction=net.net_fraction if net is not None else None,
        gross_quote=notional * grid.step_fraction if notional is not None else None,
        net_quote=(
            notional * net.net_fraction
            if notional is not None and net is not None
            else None
        ),
        state=state,
    )


def _summary(
    params: GridParams, rows: tuple[LadderRow, ...], maker_fee: Decimal | None
) -> LadderSummary:
    steps = [row.step_fraction for row in rows]
    cycles = [
        row.net_quote if maker_fee is not None else row.gross_quote for row in rows
    ]
    known = [value for value in cycles if value is not None]
    return LadderSummary(
        spacing=params.spacing,
        smallest_step_fraction=min(steps),
        largest_step_fraction=max(steps),
        maker_fee=maker_fee,
        average_cycle_quote=sum(known, _ZERO) / len(known)
        if len(known) == len(cycles)
        else None,
    )


def _notionals(
    bot: BotSnapshot, params: GridParams, levels: tuple[Decimal, ...]
) -> tuple[Decimal | None, ...]:
    """What each grid's buy leg is worth: `derive`'s `capital_per_level` for an inventory
    venue, the one base quantity of a position venue at the grid's own buy price."""
    profile = venue_profile_of(bot.venue)
    if profile is None:
        return (None,) * (len(levels) - 1)
    per_level = params.capital_quote * params.leverage / params.grid_count
    if profile.exposure_kind is ExposureKind.INVENTORY:
        return (per_level,) * (len(levels) - 1)
    quantity = per_level / params.upper
    return tuple(quantity * buy for buy in levels[:-1])


def _states(
    levels: tuple[Decimal, ...], progress: BotProgress | None
) -> tuple[tuple[LadderState, ...], str]:
    grids = len(levels) - 1
    if progress is None:
        return (LadderState.NOT_RECORDED,) * grids, ""
    if not _is_this_ladder(levels, progress.orders):
        return (LadderState.NOT_RECORDED,) * grids, RUN_DIFFERS_NOTE
    by_level = {order.level: order for order in progress.orders}
    return tuple(
        _state_of(by_level.get(i), by_level.get(i + 1)) for i in range(grids)
    ), ""


def _is_this_ladder(
    levels: tuple[Decimal, ...], orders: tuple[BotOrderLine, ...]
) -> bool:
    """Whether every resting order sits on the rung of the saved parameters it is recorded at,
    within half the smallest step (the tick rounding moves a price by less than one tick)."""
    tolerance = min(upper - lower for lower, upper in pairwise(levels)) * _HALF
    return all(
        0 <= order.level < len(levels)
        and abs(order.price - levels[order.level]) <= tolerance
        for order in orders
    )


def _state_of(lower: BotOrderLine | None, upper: BotOrderLine | None) -> LadderState:
    buys = lower is not None and lower.side == "BUY"
    sells = upper is not None and upper.side == "SELL"
    if buys and sells:
        return LadderState.WAITING_BOTH
    if buys:
        return LadderState.WAITING_TO_BUY
    if sells:
        return LadderState.WAITING_TO_SELL
    return LadderState.NO_ORDER


def _position(params: GridParams, bot: BotSnapshot, now: datetime) -> PricePosition:
    progress = bot.progress
    last = progress.mark_price if progress else None
    heard_at = progress.mark_price_at if progress else None
    profile = venue_profile_of(bot.venue)
    return PricePosition(
        last_price=last,
        age_seconds=(
            max(int((now - heard_at).total_seconds()), 0)
            if last is not None and heard_at is not None
            else None
        ),
        lower=_mark(params.lower, last),
        upper=_mark(params.upper, last),
        stop_loss=_optional_mark(params.stop_loss_price, last),
        take_profit=_optional_mark(params.take_profit_price, last),
        has_liquidation_price=(
            profile is not None and profile.exposure_kind is ExposureKind.POSITION
        ),
    )


def _mark(price: Decimal, last: Decimal | None) -> PriceMark:
    return PriceMark(price, (price - last) / last if last else None)


def _optional_mark(price: Decimal | None, last: Decimal | None) -> PriceMark | None:
    return None if price is None else _mark(price, last)
