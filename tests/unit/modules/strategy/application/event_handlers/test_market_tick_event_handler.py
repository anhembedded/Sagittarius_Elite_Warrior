"""`MarketTickEventHandler` is an adapter, and these tests hold it to that.

`EPIC-022A` moved the symbol/interval filtering, the `on_tick()` call and
the hand-off to `LiveTradingCoordinator` into `LiveStrategySession`, so
the assertions that used to live here (including `BUG-085`'s
interleaved-interval regressions) moved with them, to
`tests/unit/modules/strategy/application/services/test_live_strategy_session.py`.
What stays here is what this class still owns: log level, delegating every
tick to the session with no symbol/interval filter, and routing each tick to
the sessions of its own market only (`EPIC-028C`).

`EPIC-025` PR 2.1c-2 moved this file from `tests/unit/application/
event_handlers/` with its subject, tier unchanged. **That the handler is
subscribed at all** is a different claim and is not this file's — a test
constructing its own subject can say nothing about whether production
builds one (`CS-002`), so the subscription has its own test next to the
module that now owns it:
`tests/unit/modules/strategy/test_module_tick_subscription.py`.
"""

import logging
from datetime import UTC, datetime
from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.event_handlers.market_tick_event_handler import (
    MarketTickEventHandler,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.venue_strategy_sessions import (
    VenueStrategySessions,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: `logging-rule.md` §6: `TRACE(5)`, one below `DEBUG`.
_TRACE = 5


def _market_data(
    symbol: str = "BTCUSDT", interval: str = TimeFrame.ONE_MINUTE.value
) -> MarketData:
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
    )


def test_a_tick_logs_nothing_above_trace(caplog):
    """`BUG-163` (`logging-rule.md` §6): this runs for every tick of every
    streamed symbol, armed strategy or not — the line used to be `DEBUG`
    (`BUG-042` had already banned `INFO`), two lines per tick with the
    websocket's own, enough to bury a `--dev` log. Per-tick detail is `TRACE`,
    which only `--debug` turns on."""
    handler = MarketTickEventHandler(VenueStrategySessions(lambda _venue: Mock()))
    event = MarketTickEvent(
        market_data=_market_data(),
        market_type=MarketType.SPOT,
        market_data_venue=MarketDataVenue.SPOT_TESTNET,
    )

    with caplog.at_level(logging.DEBUG, logger="App.TradingStrategy"):
        handler.handle(event)
    assert caplog.records == []

    with caplog.at_level(_TRACE, logger="App.TradingStrategy"):
        handler.handle(event)
    (record,) = caplog.records
    assert record.levelno == _TRACE
    assert "Processing spot tick for BTCUSDT" in record.getMessage()


def test_every_tick_is_handed_to_the_session_unfiltered():
    """The handler deliberately does NOT pre-filter by symbol/interval:
    `LiveStrategySession` owns that decision because it is the only place
    that can read the armed config and the engine as one consistent
    snapshot (`EPIC-022A`). A handler that filtered too would be a second
    copy of the rule, free to disagree with the first."""
    session = Mock()
    sessions = VenueStrategySessions(lambda _venue: session)
    sessions.get(TradingVenue.FUTURES_TESTNET)
    handler = MarketTickEventHandler(sessions)
    event = MarketTickEvent(
        market_data=_market_data("ETHUSDT"),
        market_type=MarketType.FUTURES_USD_M,
        market_data_venue=MarketDataVenue.FUTURES_TESTNET,
    )

    handler.handle(event)

    session.dispatch_tick.assert_called_once_with(event.market_data)


def _sessions_on_both_venues() -> tuple[VenueStrategySessions, dict]:
    built: dict[TradingVenue, Mock] = {}

    def _build(venue: TradingVenue) -> Mock:
        built[venue] = Mock()
        return built[venue]

    sessions = VenueStrategySessions(_build)
    sessions.get(TradingVenue.FUTURES_TESTNET)
    sessions.get(TradingVenue.SPOT_TESTNET)
    return sessions, built


def test_a_spot_candle_never_drives_the_strategy_armed_on_futures():
    """`EPIC-028C` — `BTCUSDT@1m` exists on both markets at two prices, and
    both streams publish onto one bus. The Spot candle reaches Spot's session
    and nothing else."""
    sessions, built = _sessions_on_both_venues()
    event = MarketTickEvent(
        market_data=_market_data(),
        market_type=MarketType.SPOT,
        market_data_venue=MarketDataVenue.SPOT_TESTNET,
    )

    MarketTickEventHandler(sessions).handle(event)

    built[TradingVenue.SPOT_TESTNET].dispatch_tick.assert_called_once_with(
        event.market_data
    )
    built[TradingVenue.FUTURES_TESTNET].dispatch_tick.assert_not_called()


def test_a_futures_candle_reaches_only_the_futures_session():
    sessions, built = _sessions_on_both_venues()
    event = MarketTickEvent(
        market_data=_market_data(),
        market_type=MarketType.FUTURES_USD_M,
        market_data_venue=MarketDataVenue.FUTURES_TESTNET,
    )

    MarketTickEventHandler(sessions).handle(event)

    built[TradingVenue.FUTURES_TESTNET].dispatch_tick.assert_called_once_with(
        event.market_data
    )
    built[TradingVenue.SPOT_TESTNET].dispatch_tick.assert_not_called()


def test_a_tick_builds_no_session_for_a_venue_never_asked_for():
    """A venue that never had a session built gets none built by a tick."""
    built: dict[TradingVenue, Mock] = {}

    def _build(venue: TradingVenue) -> Mock:
        built[venue] = Mock()
        return built[venue]

    sessions = VenueStrategySessions(_build)
    sessions.get(TradingVenue.FUTURES_TESTNET)

    MarketTickEventHandler(sessions).handle(
        MarketTickEvent(
            market_data=_market_data(),
            market_type=MarketType.SPOT,
            market_data_venue=MarketDataVenue.SPOT_TESTNET,
        )
    )

    assert set(built) == {TradingVenue.FUTURES_TESTNET}


def _sessions_on_every_spot_venue() -> tuple[VenueStrategySessions, dict]:
    built: dict[TradingVenue, Mock] = {}

    def _build(venue: TradingVenue) -> Mock:
        built[venue] = Mock()
        return built[venue]

    sessions = VenueStrategySessions(_build)
    sessions.get(TradingVenue.SPOT_TESTNET)
    sessions.get(TradingVenue.SPOT_MAINNET)
    return sessions, built


def test_a_testnet_candle_never_drives_the_strategy_armed_on_mainnet():
    """`BUG-172` — Spot Testnet's `BTCUSDT@1m` and Spot Mainnet's are two series
    on one bus. A mainnet strategy fed a testnet candle would send a real order
    on a price that market never had."""
    sessions, built = _sessions_on_every_spot_venue()
    event = MarketTickEvent(
        market_data=_market_data(),
        market_type=MarketType.SPOT,
        market_data_venue=MarketDataVenue.SPOT_TESTNET,
    )

    MarketTickEventHandler(sessions).handle(event)

    built[TradingVenue.SPOT_TESTNET].dispatch_tick.assert_called_once_with(
        event.market_data
    )
    built[TradingVenue.SPOT_MAINNET].dispatch_tick.assert_not_called()


def test_a_mainnet_candle_never_drives_the_strategy_armed_on_the_testnet():
    sessions, built = _sessions_on_every_spot_venue()
    event = MarketTickEvent(
        market_data=_market_data(),
        market_type=MarketType.SPOT,
        market_data_venue=MarketDataVenue.MAINNET_PUBLIC,
    )

    MarketTickEventHandler(sessions).handle(event)

    built[TradingVenue.SPOT_MAINNET].dispatch_tick.assert_called_once_with(
        event.market_data
    )
    built[TradingVenue.SPOT_TESTNET].dispatch_tick.assert_not_called()


def test_a_session_of_a_venue_with_no_market_is_never_asked_for_its_source():
    """`TradingVenue.DISABLED` trades no market and has no source to read; a
    session stored under it must not make every tick raise."""
    sessions = VenueStrategySessions(lambda _venue: Mock())
    sessions.get(TradingVenue.DISABLED)
    sessions.get(TradingVenue.SPOT_TESTNET)

    reached = sessions.built_for(MarketType.SPOT, MarketDataVenue.SPOT_TESTNET)

    assert len(reached) == 1
