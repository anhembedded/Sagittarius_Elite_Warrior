"""`EPIC-035P` (audit L1) — a fill the stream delivers twice counts once.

A websocket that reconnects, or a cluster that redelivers, can send the same
`executionReport` again. Counting it twice inflates the bot's inventory past
what it holds, so the counter SELL the bot then owes is refused by the trading
budget and the bot halts. The exchange's trade id (`"t"`) says which fill a
report is: the same (order, trade) pair is the same fill, whoever reports it —
the stream, a replay, or the reconciler catching up after a gap.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.event_handlers.bot_event_router import (
    BotEventRouter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_books import (
    OwnerBooks,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trade_record import (
    TradeRecord,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.gap_world import (
    partly_filled_in_the_gap,
    running,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
    VENUE,
    GridWorld,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

S = BotLifecycleState
_AT = datetime(2026, 10, 4, 9, tzinfo=UTC)
_PARTIAL = Decimal("0.003")


def _buy_at_110(world: GridWorld) -> tuple[str, Order]:
    """The resting BUY at 110: its id, and the order as the stream reports it."""
    resting = world.book.open[world.open_ids_by_price()[Decimal(110)]]
    reported = Order(
        resting.client_order_id,
        SYMBOL,
        resting.side,
        resting.order_type,
        resting.quantity,
        status=OrderStatus.PARTIALLY_FILLED,
        price=Decimal(110),
    )
    return resting.client_order_id, reported


def _fill(world: GridWorld, quantity: Decimal, trade_id: int | None) -> BotOrderFill:
    order_id, _ = _buy_at_110(world)
    return BotOrderFill(
        order_id,
        world.book.open[order_id].side,
        Decimal(110),
        quantity,
        Decimal(0),
        "USDT",
        trade_id=trade_id,
    )


def _executed_at_110(world: GridWorld) -> Decimal:
    level = next(lv for lv in world.runtime().levels if lv.price == Decimal(110))
    assert level.order is not None
    return level.order.executed


def test_a_duplicated_partial_fill_is_counted_once() -> None:
    """Red before: the same trade, delivered twice, was booked twice."""
    world = running()
    before = world.runtime().inventory

    world.executor.facts.on_fill(_fill(world, _PARTIAL, trade_id=11))
    world.executor.facts.on_fill(_fill(world, _PARTIAL, trade_id=11))

    assert _executed_at_110(world) == _PARTIAL
    assert world.runtime().inventory == before + _PARTIAL
    assert world.state() is S.RUNNING


def test_two_different_trades_of_one_order_both_count() -> None:
    world = running()
    before = world.runtime().inventory

    world.executor.facts.on_fill(_fill(world, _PARTIAL, trade_id=11))
    world.executor.facts.on_fill(_fill(world, _PARTIAL, trade_id=12))

    assert _executed_at_110(world) == 2 * _PARTIAL
    assert world.runtime().inventory == before + 2 * _PARTIAL


def test_a_fill_without_a_trade_id_is_never_taken_for_a_duplicate() -> None:
    """A venue that reports no trade id (Futures): two equal fills are two
    fills; nothing is guessed from the quantity."""
    world = running()

    world.executor.facts.on_fill(_fill(world, _PARTIAL, trade_id=None))
    world.executor.facts.on_fill(_fill(world, _PARTIAL, trade_id=None))

    assert _executed_at_110(world) == 2 * _PARTIAL


def test_the_same_trade_id_on_another_order_is_another_fill() -> None:
    """The key is the pair (order, trade), as the audit asks: ids of two
    different orders may meet, and neither is a duplicate of the other."""
    world = running()
    ids = world.open_ids_by_price()
    before = world.runtime().inventory
    for price in (Decimal(100), Decimal(110)):
        order = world.book.open[ids[price]]
        world.executor.facts.on_fill(
            BotOrderFill(
                order.client_order_id,
                order.side,
                price,
                _PARTIAL,
                Decimal(0),
                "USDT",
                trade_id=11,
            )
        )

    assert world.runtime().inventory == before + 2 * _PARTIAL


def test_a_duplicate_stream_event_reaches_the_bot_once_through_the_real_path() -> None:
    """The venue's emitter, the bus and the router as the app wires them: the
    trade id the stream parsed reaches the bot's facts. Red before: the event
    dropped it, so nothing could tell the second report from a new fill."""
    world = running()
    before = world.runtime().inventory
    bus = MemoryEventBus()
    router = BotEventRouter(world.store, BotExecutors(world.factory))
    bus.on(OrderFilledEvent, router.on_fill)
    emitter = VenueEventEmitter(bus, VENUE, OwnerBooks())
    _, reported = _buy_at_110(world)

    for _ in range(2):
        emitter.order_filled(reported, (Decimal(110), _PARTIAL), None, 11)

    assert world.runtime().inventory == before + _PARTIAL


def test_a_fill_the_reconciler_replayed_is_not_counted_again_by_the_stream() -> None:
    """The replay uses the same key. Trade 11 was counted live; trade 12 was
    missed in a gap and the reconcile applied it from history; the stream then
    delivers trade 12 after all. Red before: 12 was counted twice."""
    world = running()
    before = world.runtime().inventory
    world.executor.facts.on_fill(_fill(world, _PARTIAL, trade_id=11))
    missed = Decimal("0.002")
    partly_filled_in_the_gap(world, Decimal(110), str(_PARTIAL + missed))
    order_id, _ = _buy_at_110(world)
    world.activity.trades.extend(
        TradeRecord(
            SYMBOL,
            trade_id,
            9,
            world.book.open[order_id].side,
            Decimal(110),
            quantity,
            quantity * 110,
            Decimal(0),
            "USDT",
            _AT,
        )
        for trade_id, quantity in ((11, _PARTIAL), (12, missed))
    )
    world.derive(str(before + _PARTIAL + missed))
    world.hold(str(before + _PARTIAL + missed))

    world.executor.facts.reconcile_after_gap()
    assert world.runtime().inventory == before + _PARTIAL + missed
    world.executor.facts.on_fill(_fill(world, missed, trade_id=12))
    world.executor.facts.on_fill(_fill(world, _PARTIAL, trade_id=11))

    assert world.runtime().inventory == before + _PARTIAL + missed
    assert _executed_at_110(world) == _PARTIAL + missed
