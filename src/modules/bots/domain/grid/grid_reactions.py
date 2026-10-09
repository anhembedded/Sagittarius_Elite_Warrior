"""`EPIC-029E` — what a Grid does about each thing that happens to its ladder.

Pure functions: each takes the runtime and one fact, and returns the runtime
after it with the actions the executor must take (`Reaction`). The executor
performs the actions through trading; nothing here sends, waits or reads a
clock. The backtest (`EPIC-029D`) can drive the same functions.

  · **A fill** accumulates on its order (ADR D10). Only the fill that
    completes the order is a full fill, and only it emits the counter order:
    a full BUY at level i owes a SELL at i + 1 of what it bought net of the
    base-asset fee; a full SELL at i owes a BUY at i − 1 of that level's
    `buy_quantity`. Exactly one counter order per full fill, however many
    partial events made it up. A fill for an order the ladder does not hold
    (a late duplicate, another owner's) changes nothing.
  · **Profit is booked once per completed cycle**, when the counter SELL of a
    ladder BUY fills: `(sell − buy) × quantity − both legs' fees`, the
    per-grid profit of `grid_derived.py`. A SELL of base the opening bought
    has no ladder buy and books no grid profit; it still moves the inventory.
  · **An order ending without filling** is re-placed once for what it still
    owes. A second end at the same level within a minute halts the bot
    (`LEVEL_KEEPS_ENDING`); a rejection halts it at once (`ORDER_REJECTED`).
    What is owed worth less than the exchange's NOTIONAL minimum is never
    re-placed (Binance would refuse it): the level is settled for what it
    executed, and its counter order goes out if it clears the minimum.
  · **While placing is held** (PAUSED), a counter order or a re-placement is
    kept in `held` instead of emitted; `release_held` emits them on resume.
    A second order held for a level that already has one (the price crossed
    it both ways while paused) halts: released together they would be a
    crossing pair from one account, and a resume re-plans instead (D13).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelEvent,
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
    HeldOrder,
    LevelOrder,
    RuntimeLevel,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_quantity_rounding_policy import (
    OrderQuantityRoundingPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

_ROUNDING = OrderQuantityRoundingPolicy()
_ZERO = Decimal(0)
#: Two ends at one level inside this window halt the bot (ADR §3.2).
LEVEL_END_WINDOW = timedelta(minutes=1)


@dataclass(frozen=True, slots=True)
class PlaceOrder:
    """Send a LIMIT GTC order for a level."""

    level_index: int
    side: OrderSide
    price: Decimal
    quantity: Decimal
    paired_buy_price: Decimal | None = None
    paired_buy_fee_quote: Decimal = _ZERO
    #: What an earlier order at the level executed (a re-placement).
    carried_executed: Decimal = _ZERO
    carried_base_fee: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class Halt:
    """Stop acting and halt the bot, naming why."""

    reason: GridReason
    detail: str


type GridAction = PlaceOrder | Halt


@dataclass(frozen=True, slots=True)
class Reaction:
    """The runtime after one fact, and what the executor must do about it."""

    runtime: GridRuntime
    actions: tuple[GridAction, ...] = ()


@dataclass(frozen=True, slots=True)
class LevelFill:
    """One fill of one order, its fees split by the asset they were paid in.
    A fee in a third asset (BNB) is not counted here; the event keeps it."""

    client_order_id: str
    price: Decimal
    quantity: Decimal
    base_fee: Decimal = _ZERO
    quote_fee: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class LevelEnd:
    """An order that ended without filling whole, and when."""

    client_order_id: str
    at: datetime
    #: The exchange's reason when it refused the order outright.
    rejection: str | None = None


@dataclass(frozen=True, slots=True)
class LadderRules:
    """The symbol's exchange filters a reaction must respect: LOT_SIZE's step
    and the NOTIONAL minimum, below which Binance refuses an order."""

    step_size: Decimal
    min_notional: Decimal


def placed(
    runtime: GridRuntime, action: PlaceOrder, client_order_id: str
) -> GridRuntime:
    """The level after its order was sent with `client_order_id` (EMPTY → PLACING)."""
    order = LevelOrder(
        client_order_id,
        action.side,
        action.price,
        action.quantity,
        carried_executed=action.carried_executed,
        carried_base_fee=action.carried_base_fee,
        paired_buy_price=action.paired_buy_price,
        paired_buy_fee_quote=action.paired_buy_fee_quote,
    )
    return runtime.updating_level(
        action.level_index, lambda level: level.moved(LevelEvent.PLACE, order)
    )


def accepted(runtime: GridRuntime, client_order_id: str) -> GridRuntime:
    """The level after trading accepted its order (PLACING → RESTING)."""
    level = runtime.level_of(client_order_id)
    if level is None or level.state is not LevelState.PLACING:
        return runtime
    return runtime.with_level(level.moved(LevelEvent.ACCEPTED_OR_RESTING, level.order))


def on_fill(
    runtime: GridRuntime, fill: LevelFill, step_size: Decimal, hold: bool
) -> Reaction:
    """The ladder after one fill; on a full fill, the counter order it owes."""
    level = runtime.level_of(fill.client_order_id)
    if level is None or level.order is None:
        return Reaction(runtime)
    order = replace(
        level.order,
        executed=level.order.executed + fill.quantity,
        base_fee=level.order.base_fee + fill.base_fee,
        quote_fee=level.order.quote_fee + fill.quote_fee,
    )
    after = _book_inventory(runtime, order.side, fill)
    if not order.is_filled:
        return Reaction(after.with_level(level.moved(LevelEvent.PARTIAL_FILL, order)))
    filled = level.moved(LevelEvent.FULL_FILL, order)
    after = after.with_level(filled.moved(LevelEvent.SETTLED, None))
    if order.side is OrderSide.SELL:
        after = _book_cycle(after, order, fill.price)
    counter = _counter(after, level.index, order, step_size)
    if counter is None:
        return Reaction(after)
    return _emit(after, counter, hold)


def on_end(
    runtime: GridRuntime, end: LevelEnd, rules: LadderRules, hold: bool
) -> Reaction:
    """The ladder after an order ended without filling whole."""
    level = runtime.level_of(end.client_order_id)
    if level is None or level.order is None:
        return Reaction(runtime)
    order = level.order
    recent = tuple(t for t in level.ended_at if end.at - t < LEVEL_END_WINDOW)
    emptied = replace(level.moved(LevelEvent.ENDED, None), ended_at=(*recent, end.at))
    after = runtime.with_level(emptied)
    if end.rejection is not None:
        return _halt(
            after, GridReason.ORDER_REJECTED, f"L{level.index}: {end.rejection}"
        )
    if recent:
        return _halt(
            after,
            GridReason.LEVEL_KEEPS_ENDING,
            f"L{level.index}: two orders ended within a minute",
        )
    owed = order.quantity - order.executed
    if order.executed == 0 or owed * order.price >= rules.min_notional:
        again = PlaceOrder(
            level.index,
            order.side,
            order.price,
            owed,
            order.paired_buy_price,
            order.paired_buy_fee_quote,
            carried_executed=order.total_executed,
            carried_base_fee=order.total_base_fee,
        )
        return _emit(after, again, hold)
    return _settle_short(after, level.index, order, rules, hold)


def _settle_short(
    runtime: GridRuntime,
    index: int,
    order: LevelOrder,
    rules: LadderRules,
    hold: bool,
) -> Reaction:
    """What is owed is worth less than the exchange minimum, so the level is
    done for what it executed: a SELL books its cycle, and the counter order
    goes out if it clears the minimum (else the executed part stays in the
    inventory with no level, and a stop sells or keeps it)."""
    if order.side is OrderSide.SELL:
        runtime = _book_cycle(runtime, order, order.price)
    counter = _counter(runtime, index, order, rules.step_size)
    if counter is None:
        return Reaction(runtime)
    if (
        isinstance(counter, PlaceOrder)
        and counter.quantity * counter.price < rules.min_notional
    ):
        return Reaction(runtime)
    return _emit(runtime, counter, hold)


def release_held(runtime: GridRuntime) -> Reaction:
    """The orders a pause held back, ready to place (resume)."""
    actions = tuple(
        PlaceOrder(
            held.level_index,
            held.side,
            runtime.levels[held.level_index].price,
            held.quantity,
            held.paired_buy_price,
            held.paired_buy_fee_quote,
            held.carried_executed,
            held.carried_base_fee,
        )
        for held in runtime.held
    )
    return Reaction(replace(runtime, held=()), actions)


def drop_order(runtime: GridRuntime, client_order_id: str) -> GridRuntime:
    """The level after its order is gone with nothing owed: trading refused or
    failed to send it, or the bot's own stop cancelled it."""
    level = runtime.level_of(client_order_id)
    if level is None:
        return runtime
    return runtime.with_level(level.moved(LevelEvent.ENDED, None))


def adopted(runtime: GridRuntime, index: int, order: LevelOrder) -> GridRuntime:
    """The level after reconciliation adopted an order carrying the bot's tag
    that the saved ladder did not know (ADR §3.3 step 5; EMPTY → RESTING).

    A counter order held for this level is dropped: the adopted order *is* it,
    sent before the app died and never saved, so placing the held one too
    would put two orders at one level."""
    after = runtime.updating_level(
        index, lambda level: level.moved(LevelEvent.ADOPT, order)
    )
    return replace(after, held=tuple(h for h in after.held if h.level_index != index))


def book_market_fill(
    runtime: GridRuntime, side: OrderSide, fill: LevelFill
) -> GridRuntime:
    """The inventory after a fill of one of the bot's market orders (the
    opening buy, an exit slice): no level holds it, and it owes no counter."""
    return _book_inventory(runtime, side, fill)


def _book_inventory(
    runtime: GridRuntime, side: OrderSide, fill: LevelFill
) -> GridRuntime:
    if side is OrderSide.BUY:
        return replace(
            runtime,
            inventory=runtime.inventory + fill.quantity - fill.base_fee,
            cost=runtime.cost + fill.price * fill.quantity + fill.quote_fee,
        )
    average = runtime.average_cost or _ZERO
    sold = min(fill.quantity + fill.base_fee, runtime.inventory)
    earned = fill.price * fill.quantity - fill.quote_fee - average * sold
    return replace(
        runtime,
        inventory=runtime.inventory - sold,
        cost=runtime.cost - average * sold,
        realised_total=runtime.realised_total + earned,
    )


def _book_cycle(runtime: GridRuntime, sell: LevelOrder, price: Decimal) -> GridRuntime:
    if sell.paired_buy_price is None:
        return runtime
    quantity = sell.total_executed
    sell_fee_quote = sell.quote_fee + sell.total_base_fee * price
    profit = (
        (sell.price - sell.paired_buy_price) * quantity
        - sell_fee_quote
        - sell.paired_buy_fee_quote
    )
    return replace(
        runtime,
        realised_profit=runtime.realised_profit + profit,
        completed_cycles=runtime.completed_cycles + 1,
    )


def _counter(
    runtime: GridRuntime, index: int, filled: LevelOrder, step_size: Decimal
) -> PlaceOrder | Halt | None:
    if filled.side is OrderSide.BUY:
        target = index + 1
        quantity = _ROUNDING.round_quantity_down(
            filled.total_executed - filled.total_base_fee, step_size
        )
        fee_quote = filled.quote_fee + filled.total_base_fee * filled.price
        paired: tuple[Decimal | None, Decimal] = (filled.price, fee_quote)
        side = OrderSide.SELL
    else:
        target = index - 1
        quantity = runtime.levels[target].buy_quantity if target >= 0 else _ZERO
        paired = (None, _ZERO)
        side = OrderSide.BUY
    if not 0 <= target < len(runtime.levels) or quantity <= 0:
        return None
    level: RuntimeLevel = runtime.levels[target]
    if level.state is not LevelState.EMPTY:
        return Halt(
            GridReason.DUPLICATE_LEVEL_ORDER,
            f"L{target} already holds an order; the counter of L{index} cannot go there",
        )
    return PlaceOrder(target, side, level.price, quantity, *paired)


def hold_order(runtime: GridRuntime, action: PlaceOrder) -> Reaction:
    """The ladder with `action` kept back for a resume instead of placed: what
    a pause does with an order the exchange would not take (`EPIC-035E`)."""
    return _emit(runtime, action, hold=True)


def _emit(runtime: GridRuntime, action: PlaceOrder | Halt, hold: bool) -> Reaction:
    if isinstance(action, Halt):
        return _halt(runtime, action.reason, action.detail)
    if hold:
        if any(h.level_index == action.level_index for h in runtime.held):
            return _halt(
                runtime,
                GridReason.DUPLICATE_LEVEL_ORDER,
                f"L{action.level_index} already has a held order; the price "
                "crossed it both ways while paused",
            )
        held = HeldOrder(
            action.level_index,
            action.side,
            action.quantity,
            action.paired_buy_price,
            action.paired_buy_fee_quote,
            action.carried_executed,
            action.carried_base_fee,
        )
        return Reaction(replace(runtime, held=(*runtime.held, held)))
    return Reaction(runtime, (action,))


def _halt(runtime: GridRuntime, reason: GridReason, detail: str) -> Reaction:
    return Reaction(runtime.with_reason(reason, detail), (Halt(reason, detail),))
