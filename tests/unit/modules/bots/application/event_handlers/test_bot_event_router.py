"""`EPIC-029E` — the bots' one bus listener routes each event to its bot (ADR D9, D12).

Real `BotEventRouter` and real executors over the simulated venue: a fill or an
end reaches the bot whose tag its id carries, on its own venue only, and a
restored bot gets its executor on the spot; a tick reaches the bots trading that
symbol on that market; a switch-off halts the venue's bots and a switch-on wakes
the stored ones.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.application.event_handlers.bot_event_router import (
    BotEventRouter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_rejected_event import (
    OrderRejectedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    SYMBOL,
    VENUE,
    GridWorld,
    grid_world,
)

S = BotLifecycleState
_AT = datetime(2026, 10, 4, 9, tzinfo=UTC)


def _routed(state: BotLifecycleState = S.STARTING) -> tuple[GridWorld, BotRouterParts]:
    world = grid_world(state=state)
    executors = BotExecutors(world.factory)
    return world, BotRouterParts(BotEventRouter(world.store, executors), executors)


class BotRouterParts:
    def __init__(self, router: BotEventRouter, executors: BotExecutors) -> None:
        self.router = router
        self.executors = executors


def _running() -> tuple[GridWorld, BotRouterParts]:
    world, parts = _routed()
    store_bot = world.store.load_all().bots[0].bot
    parts.executors.for_bot(store_bot).start()
    assert world.state() is S.RUNNING
    world.book.requests.clear()
    return world, parts


def _order(
    world: GridWorld, price: Decimal, status: OrderStatus = OrderStatus.FILLED
) -> Order:
    order = world.book.open[world.open_ids_by_price()[price]]
    return Order(
        order.client_order_id,
        SYMBOL,
        order.side,
        order.order_type,
        order.quantity,
        status=status,
        price=price,
    )


def _tick(symbol: str, close: float, market: MarketType) -> MarketTickEvent:
    return MarketTickEvent(
        market_data=MarketData(
            symbol=symbol,
            interval="1m",
            open_time=_AT,
            open_price=close,
            high_price=close,
            low_price=close,
            close_price=close,
            volume=1.0,
            close_time=_AT,
            quote_asset_volume=1.0,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.0,
            taker_buy_quote_asset_volume=0.0,
        ),
        market_type=market,
    )


def test_a_fill_of_the_bots_order_reaches_it_and_its_counter_follows() -> None:
    world, parts = _running()
    order = _order(world, Decimal(110))
    world.book.open.pop(order.client_order_id)

    parts.router.on_fill(
        OrderFilledEvent(order, Decimal(110), Decimal("2.272"), venue=VENUE)
    )

    assert [(r.side.value, r.reference_price) for r in world.book.requests] == [
        ("SELL", Decimal(120))
    ]


def test_a_fill_on_another_venue_or_untagged_reaches_no_bot() -> None:
    world, parts = _running()
    order = _order(world, Decimal(110))
    untagged = Order(
        ClientOrderId("SEW-0123456789ab"),
        SYMBOL,
        order.side,
        order.order_type,
        order.quantity,
    )

    parts.router.on_fill(
        OrderFilledEvent(
            order, Decimal(110), Decimal("2.272"), venue=TradingVenue.FUTURES_TESTNET
        )
    )
    parts.router.on_fill(
        OrderFilledEvent(untagged, Decimal(110), Decimal(1), venue=VENUE)
    )

    assert world.book.requests == []


def test_a_rejection_halts_the_bot_with_the_exchanges_reason() -> None:
    world, parts = _running()

    parts.router.on_rejected(
        OrderRejectedEvent(
            _order(world, Decimal(140)), "insufficient balance", venue=VENUE
        )
    )

    assert world.state() is S.HALTED
    assert "insufficient balance" in world.runtime().reason_detail


def test_an_end_reported_as_rejected_halts_too() -> None:
    world, parts = _running()

    parts.router.on_end(
        OrderEndedEvent(_order(world, Decimal(140), OrderStatus.REJECTED), venue=VENUE)
    )

    assert world.state() is S.HALTED


def test_a_restored_bot_gets_an_executor_when_its_fill_arrives() -> None:
    before = grid_world()
    before.executor.start()
    world, parts = _routed()
    world.store.save(before.store.load_all().bots[0])
    world.book.open = dict(before.book.open)
    assert parts.executors.get(BOT) is None

    order = _order(world, Decimal(110))
    parts.router.on_fill(OrderFilledEvent(order, Decimal(110), Decimal(1), venue=VENUE))

    assert parts.executors.get(BOT) is not None


def test_a_tick_reaches_the_bot_on_its_symbol_and_market_only() -> None:
    world, parts = _running()

    parts.router.on_tick(_tick("ETHUSDT", 89.0, MarketType.SPOT))
    parts.router.on_tick(_tick(SYMBOL, 89.0, MarketType.FUTURES_USD_M))
    assert world.state() is S.RUNNING

    parts.router.on_tick(_tick(SYMBOL, 89.0, MarketType.SPOT))
    assert world.state() is S.STOPPED


def test_a_switch_off_halts_the_bots_on_that_venue() -> None:
    world, parts = _running()

    parts.router.on_switch(
        TradingSwitchChangedEvent(False, TradingSwitchCause.EMERGENCY_STOP, venue=VENUE)
    )

    assert world.state() is S.HALTED


def test_a_switch_on_wakes_every_stored_bot_on_the_venue() -> None:
    world, parts = _routed(state=S.HALTED)

    parts.router.on_switch(
        TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=VENUE)
    )

    assert parts.executors.get(BOT) is not None
    assert not world.session.claim_symbol(SYMBOL, "manual")


def test_a_switch_on_leaves_a_draft_bot_alone() -> None:
    _world, parts = _routed(state=S.DRAFT)

    parts.router.on_switch(
        TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=VENUE)
    )

    assert parts.executors.get(BOT) is None
