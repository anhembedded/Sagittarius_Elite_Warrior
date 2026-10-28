"""`EPIC-047E` (AC10, D5) - a chart's candles and ticks come from the host, never from the exchange; offline they freeze with a sentence."""

from __future__ import annotations

from dataclasses import replace

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.closed_candle_window import (
    CANDLE_WINDOW_ROOT,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.host_candle_feed import (
    OFFLINE_WORDS,
    HostCandleFeed,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.host_event_publisher import (
    HostEventPublisher,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    CandlesUnavailableError,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import Wired
from Sagittarius_Elite_Warrior.tests.unit.shell.vps_link.vps_world import (
    VpsHost,
    VpsTabWorld,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import (
    ROOTS,
    FakeCandles,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_market_data import (
    full_candle_window,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.contract.samples_operations import (
    full_market_data,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus


def _tab_with_candles(answer: Wired | None = None) -> VpsTabWorld:
    """A running world whose host keeps a candle store (the bridge reads its ports when the link opens)."""
    host = VpsHost()
    host.candles = FakeCandles()
    if answer is not None:
        host.candles.answer = answer
    return VpsTabWorld(host).start()


def _feed(tab: VpsTabWorld) -> HostCandleFeed:
    return HostCandleFeed(TradingVenue.SPOT_TESTNET, tab.world, ROOTS)


def test_history_is_the_host_stores_closed_candles_oldest_first() -> None:
    tab = _tab_with_candles()
    window = full_candle_window()

    candles = _feed(tab).load_history(window.symbol, TimeFrame.ONE_MINUTE, 50)
    tab.stop()

    assert [c.open_time for c in candles] == [c.open_time for c in window.candles]
    assert [c.close_price for c in candles] == [
        float(c.close_price) for c in window.candles
    ]
    assert all(c.is_closed for c in candles)
    assert tab.host.candles is not None
    assert tab.host.candles.asked[0].venue == TradingVenue.SPOT_TESTNET.value


def test_a_symbol_the_host_keeps_no_store_for_says_so() -> None:
    tab = _tab_with_candles(
        Wired(
            CANDLE_WINDOW_ROOT,
            replace(full_candle_window(), shard_found=False, candles=()),
        )
    )

    with pytest.raises(CandlesUnavailableError, match="not published by the host"):
        _feed(tab).load_history("BTCUSDT", TimeFrame.ONE_MINUTE, 50)
    tab.stop()


def test_offline_the_chart_freezes_with_a_sentence_and_nothing_else_is_asked() -> None:
    host = VpsHost()
    host.candles = FakeCandles()
    tab = VpsTabWorld(host, hold_after_cut=True).start()
    tab.cut()
    tab.wait_down()

    with pytest.raises(CandlesUnavailableError) as stopped:
        _feed(tab).load_history("BTCUSDT", TimeFrame.ONE_MINUTE, 50)
    tab.stop()

    assert stopped.value.reason == OFFLINE_WORDS
    assert host.candles.asked == []


def test_the_hosts_forming_candles_tick_on_the_bus_and_a_bot_event_follows_the_file() -> (
    None
):
    bus = MemoryEventBus()
    ticks: list[MarketTickEvent] = []
    changes: list[BotChangedEvent] = []
    bus.on(MarketTickEvent, ticks.append)
    bus.on(BotChangedEvent, changes.append)
    publisher = HostEventPublisher(bus)
    market = full_market_data()

    publisher.on_market(market)
    publisher.on_bot_changed("b-0001", True)

    forming = [c for s in market.symbols for c in s.forming]
    assert len(ticks) == len(forming)
    assert all(not t.market_data.is_closed for t in ticks)
    assert {t.market_data.interval for t in ticks} == {c.timeframe for c in forming}
    assert [(c.bot_id, c.removed) for c in changes] == [("b-0001", True)]
