"""`BOT-126` — `TradingPresenter._handle_market_tick` used to filter a
`MarketTickEvent` by `symbol` alone, exactly the fault `BUG-085` fixed for
`MarketTickEventHandler`. That was harmless while `ILiveStreamService` was
one process-wide stream (no two intervals for the same symbol could ever
be live at once); `BOT-126`'s per-owner subscriptions made it possible for
real (Dev Board and this screen each own their own), so this locks the
fix: a tick for the active symbol at a DIFFERENT interval must never reach
the chart.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_event_bus import IEventBus


@pytest.fixture
def event_bus() -> MemoryEventBus:
    return MemoryEventBus()


@pytest.fixture
def container(container, event_bus):
    """The shared container, with the real bus in place of an invented mock,
    so a tick reaches this screen the way production delivers it."""
    resolve_the_rest = container.resolve.side_effect

    def resolve(interface):
        if interface is IEventBus:
            return event_bus
        return resolve_the_rest(interface)

    container.resolve.side_effect = resolve
    return container


def _market_data(symbol: str = "BTCUSDT", interval: str = "1m") -> MarketData:
    dt = datetime(2023, 1, 1, tzinfo=UTC)
    return MarketData(
        symbol=symbol,
        interval=interval,
        open_time=dt,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
        volume=1000.0,
        close_time=dt,
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0,
        is_closed=True,
    )


def test_a_tick_for_the_active_symbol_at_a_different_interval_is_ignored(
    presenter, view
):
    presenter._active_symbol = "BTCUSDT"
    presenter._active_interval = "1m"
    view.chart.append_closed_candle.reset_mock()

    event = MarketTickEvent(
        market_data=_market_data("BTCUSDT", "5m"), market_type=MarketType.SPOT
    )
    presenter._handle_market_tick(event)

    view.chart.append_closed_candle.assert_not_called()


def test_a_tick_for_the_active_symbol_and_interval_reaches_the_chart(presenter, view):
    presenter._active_symbol = "BTCUSDT"
    presenter._active_interval = "1m"
    view.chart.append_closed_candle.reset_mock()

    event = MarketTickEvent(
        market_data=_market_data("BTCUSDT", "1m"), market_type=MarketType.SPOT
    )
    presenter._handle_market_tick(event)

    view.chart.append_closed_candle.assert_called_once()


def test_a_tick_for_a_different_symbol_is_still_ignored_regardless_of_interval(
    presenter, view
):
    presenter._active_symbol = "BTCUSDT"
    presenter._active_interval = "1m"
    view.chart.append_closed_candle.reset_mock()

    event = MarketTickEvent(
        market_data=_market_data("ETHUSDT", "1m"), market_type=MarketType.SPOT
    )
    presenter._handle_market_tick(event)

    view.chart.append_closed_candle.assert_not_called()


def test_the_chart_follows_the_market_of_the_venue_this_screen_shows(presenter):
    """`EPIC-028C` — `conftest.py` binds Futures Testnet: the chart syncs,
    reads and streams Futures, so a strategy armed from it trades on Futures
    prices."""
    assert presenter._chart_coordinator.chart_market is MarketType.FUTURES_USD_M


def test_a_spot_tick_on_the_bus_never_reaches_a_futures_chart(
    presenter, view, event_bus
):
    """`EPIC-028C` — the Dev Board may stream Spot `BTCUSDT@1m` while this
    screen charts Futures `BTCUSDT@1m`: same symbol, same interval, another
    price. Published on the real bus, so the Feed's filter is what decides."""
    presenter._active_symbol = "BTCUSDT"
    presenter._active_interval = "1m"
    view.chart.append_closed_candle.reset_mock()

    event_bus.emit(
        MarketTickEvent(
            market_data=_market_data("BTCUSDT", "1m"), market_type=MarketType.SPOT
        )
    )
    view.chart.append_closed_candle.assert_not_called()

    event_bus.emit(
        MarketTickEvent(
            market_data=_market_data("BTCUSDT", "1m"),
            market_type=MarketType.FUTURES_USD_M,
        )
    )
    view.chart.append_closed_candle.assert_called_once()
