"""`EPIC-039G` — what a Futures run pays reaches its account once, and funding stays apart.

A fill's commission reaches the PnL from exactly one record of the trade, keyed by the
exchange's trade id; funding is a wallet event that is booked beside the grid profit, never
inside it; and a Spot run's existing figures do not move."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.event_handlers.bot_event_router import (
    BotEventRouter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    decode_runtime,
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.readiness.bot_progress_reader import (
    bot_progress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_order_events import (
    BotFundingCharge,
    BotOrderFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_pnl import pnl_summary
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.venue_event_emitter import (
    VenueEventEmitter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.owner_books import (
    OwnerBooks,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.funding_charged_event import (
    FundingChargedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_filled_event import (
    OrderFilledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.gap_world import (
    running,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    SYMBOL,
    VENUE,
    GridWorld,
    grid_world,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

_QUANTITY = Decimal("0.003")
_FEE = Decimal("0.05")


def _stored_progress(world: GridWorld):
    progress = bot_progress(world.store.load(BotId(BOT)))
    assert progress is not None and progress.pnl is not None
    return progress.pnl


def _wired(world: GridWorld) -> tuple[MemoryEventBus, VenueEventEmitter]:
    """The venue's emitter, the bus and the router as the app wires them."""
    bus = MemoryEventBus()
    router = BotEventRouter(world.store, BotExecutors(world.factory))
    bus.on(OrderFilledEvent, router.on_fill)
    bus.on(FundingChargedEvent, router.on_funding)
    return bus, VenueEventEmitter(bus, VENUE, OwnerBooks())


def _resting_buy_at_110(world: GridWorld) -> Order:
    resting = world.book.open[world.open_ids_by_price()[Decimal(110)]]
    return Order(
        resting.client_order_id,
        SYMBOL,
        resting.side,
        resting.order_type,
        resting.quantity,
        status=OrderStatus.PARTIALLY_FILLED,
        price=Decimal(110),
    )


def test_a_fill_fee_reaches_pnl_once_whichever_report_comes_first() -> None:
    """The stream delivers one trade twice (a reconnect, a duplicate): its trade id is the
    key, so the commission is counted once, at the emitter and again at the bot."""
    world = running()
    _, emitter = _wired(world)
    reported = _resting_buy_at_110(world)

    for _ in range(2):
        emitter.order_filled(
            reported, (Decimal(110), _QUANTITY), (_FEE, "USDT"), trade_id=11
        )

    assert world.runtime().commissions == _FEE


def test_the_bot_counts_a_commission_once_even_if_the_emitter_let_the_trade_through() -> (
    None
):
    world = running()
    order = _resting_buy_at_110(world)
    fill = BotOrderFill(
        order.client_order_id,
        order.side,
        Decimal(110),
        _QUANTITY,
        _FEE,
        "USDT",
        trade_id=11,
    )

    world.executor.facts.on_fill(fill)
    world.executor.facts.on_fill(fill)

    assert world.runtime().commissions == _FEE


def test_two_different_trades_each_pay_their_commission() -> None:
    world = running()
    order = _resting_buy_at_110(world)

    for trade_id in (11, 12):
        world.executor.facts.on_fill(
            BotOrderFill(
                order.client_order_id,
                order.side,
                Decimal(110),
                _QUANTITY,
                _FEE,
                "USDT",
                trade_id=trade_id,
            )
        )

    assert world.runtime().commissions == 2 * _FEE


def test_a_position_across_a_funding_time_pays_or_earns_and_progress_shows_it_separately() -> (
    None
):
    world = running()
    _, emitter = _wired(world)
    before = _stored_progress(world)

    emitter.funding_charged(SYMBOL, Decimal("-0.5"))
    emitter.funding_charged(SYMBOL, Decimal("0.2"))

    pnl = _stored_progress(world)
    assert pnl.funding == Decimal("-0.3")
    assert pnl.grid_profit == before.grid_profit, "funding is not grid profit"
    assert pnl.realised == before.realised
    assert pnl.total == before.total - Decimal("0.3")


def test_funding_of_another_symbol_reaches_no_bot() -> None:
    world = running()
    _, emitter = _wired(world)

    emitter.funding_charged("ETHUSDT", Decimal(-1))

    assert world.runtime().funding_total == 0


def test_a_stopped_bot_holds_no_position_to_be_charged() -> None:
    world = grid_world(state=BotLifecycleState.STOPPED, runtime=GridRuntime(levels=()))

    world.executor.facts.on_funding(BotFundingCharge(SYMBOL, Decimal(-1)))

    assert world.runtime().funding_total == 0


def test_a_file_written_before_costs_were_counted_reads_as_nothing_counted() -> None:
    world = running()
    stored = dict(encode_runtime(world.runtime()))
    del stored["commissions"], stored["funding_total"]

    runtime = decode_runtime(stored)

    assert (runtime.commissions, runtime.funding_total) == (0, 0)


def test_the_costs_survive_a_save_and_a_load() -> None:
    world = running()
    runtime = replace(
        world.runtime(), commissions=Decimal("0.7"), funding_total=Decimal("-0.3")
    )

    again = decode_runtime(encode_runtime(runtime))

    assert (again.commissions, again.funding_total) == (Decimal("0.7"), Decimal("-0.3"))


def test_a_spot_fee_paid_in_the_base_asset_is_priced_at_the_fill_into_commissions() -> (
    None
):
    world = running()
    order = _resting_buy_at_110(world)

    world.executor.facts.on_fill(
        BotOrderFill(
            order.client_order_id,
            order.side,
            Decimal(110),
            _QUANTITY,
            Decimal("0.0001"),
            "BTC",
            trade_id=21,
        )
    )

    assert world.runtime().commissions == Decimal("0.0001") * Decimal(110)


def test_spot_pnl_is_unchanged_for_the_oracle_inputs() -> None:
    """The Spot ladder's figures are what they were: no funding exists, so the total is
    still realised plus unrealised, and the new cost lines add information, not change it."""
    world = running()
    sell = world.open_ids_by_price()[Decimal(130)]
    resting = world.book.open.pop(sell)
    world.executor.facts.on_fill(
        BotOrderFill(
            resting.client_order_id,
            resting.side,
            Decimal(130),
            resting.quantity,
            Decimal("0.1"),
            "USDT",
        )
    )
    runtime = world.runtime()

    summary = pnl_summary(runtime, Decimal(1000))

    assert summary.funding == 0
    assert summary.unrealised is not None
    assert summary.total == runtime.realised_total + summary.unrealised
    assert summary.realised == runtime.realised_total
    assert summary.grid_profit == runtime.realised_profit
    assert summary.commissions == Decimal("0.1")
