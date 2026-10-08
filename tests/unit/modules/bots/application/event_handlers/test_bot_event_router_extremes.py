"""`BUG-191` — a stop loss or take profit acts on the extremes a kline traded, not only on its close.

Binance pushes a kline update every 1–2 s carrying the close at that moment; a
wick between two pushes is visible only in the kline's `low_price` / `high_price`.
The world's stop loss is `price:90` and its take profit `price:150`. Real router,
real executor, over the simulated venue.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
    VENUE,
    GridWorld,
    grid_world,
)

S = BotLifecycleState
_BAR = datetime(2026, 10, 8, 9, tzinfo=UTC)
_NEXT_BAR = _BAR + timedelta(minutes=1)


def _kline(
    close: float, low: float, high: float, bar: datetime = _BAR
) -> MarketTickEvent:
    return MarketTickEvent(
        market_data=MarketData(
            symbol=SYMBOL,
            interval="1m",
            open_time=bar,
            open_price=close,
            high_price=high,
            low_price=low,
            close_price=close,
            volume=1.0,
            close_time=bar + timedelta(seconds=59),
            quote_asset_volume=1.0,
            number_of_trades=1,
            taker_buy_base_asset_volume=0.0,
            taker_buy_quote_asset_volume=0.0,
        ),
        market_type=MarketType.SPOT,
        market_data_venue=VENUE.market_data_venue,
    )


def _router(state: S = S.STARTING) -> tuple[GridWorld, BotEventRouter]:
    world = grid_world(state=state)
    executors = BotExecutors(world.factory)
    router = BotEventRouter(world.store, executors)
    executors.for_bot(world.store.load_all().bots[0].bot).start()
    return world, router


def test_a_wick_below_the_stop_loss_between_two_pushes_stops_the_bot() -> None:
    world, router = _router()
    assert world.state() is S.RUNNING

    router.on_tick(_kline(close=100, low=100, high=100))
    router.on_tick(_kline(close=100, low=89, high=100))

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.STOP_LOSS
    assert world.book.open == {}


def test_a_wick_above_the_take_profit_between_two_pushes_stops_the_bot() -> None:
    world, router = _router()

    router.on_tick(_kline(close=100, low=100, high=100))
    router.on_tick(_kline(close=100, low=100, high=151))

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.TAKE_PROFIT


def test_a_wick_in_the_first_push_of_a_new_bar_counts() -> None:
    world, router = _router()

    router.on_tick(_kline(close=100, low=100, high=100))
    router.on_tick(_kline(close=100, low=89, high=100, bar=_NEXT_BAR))

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.STOP_LOSS


@pytest.mark.parametrize(
    ("low", "high"), [(89, 100), (100, 151)], ids=["stop-loss", "take-profit"]
)
def test_an_extreme_from_before_the_bot_watched_never_fires_its_exit(
    low: float, high: float
) -> None:
    """The first push after a start carries the minute's low and high from before
    the bot was running: only its close counts, and so does the same extreme in
    the pushes that follow in that bar."""
    world, router = _router()

    router.on_tick(_kline(close=100, low=low, high=high))
    router.on_tick(_kline(close=101, low=low, high=high))

    assert world.state() is S.RUNNING


def test_a_new_extreme_after_a_pre_watch_wick_does_count() -> None:
    world, router = _router()

    router.on_tick(_kline(close=100, low=89, high=100))
    router.on_tick(_kline(close=100, low=88, high=100))

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.STOP_LOSS


def test_a_wick_while_starting_stops_the_bot_like_one_while_running() -> None:
    world = grid_world(state=S.STARTING)
    executors = BotExecutors(world.factory)
    executors.for_bot(world.store.load_all().bots[0].bot)
    router = BotEventRouter(world.store, executors)
    assert world.state() is S.STARTING

    router.on_tick(_kline(close=100, low=100, high=100))
    router.on_tick(_kline(close=100, low=89, high=100))

    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.STOP_LOSS
