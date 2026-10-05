"""Fixtures of the Market mode's presenter tests: the presenter built on
real fakes of its ports (`market_fixtures.py`)."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_dependencies import (
    MarketDependencies,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_presenter import (
    MarketPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_view import (
    MarketView,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.ema_20_script import (
    Ema20Script,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_scripts.rsi_14_script import (
    Rsi14Script,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.market.market_fixtures import (
    QueuedThreads,
    RecordingCandleFeed,
    presenter_container,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus

SYMBOLS = ("BTCUSDT", "ETHUSDT", "BNBUSDT")
CONNECTED = ExchangeConnectionStatus(
    venue=TradingVenue.FUTURES_TESTNET,
    reachable=True,
    failure=None,
    server_time_skew_ms=12,
    usdt_balance=None,
    position_mode=None,
    margin_type=None,
    open_position_count=0,
)


@pytest.fixture
def event_bus():
    return MemoryEventBus()


@pytest.fixture
def threads():
    return QueuedThreads()


@pytest.fixture
def feed():
    """The Spot candles, the mode's default market."""
    return RecordingCandleFeed()


@pytest.fixture
def futures_feed():
    return RecordingCandleFeed()


@pytest.fixture
def history():
    """The store the charts read beyond their first window (`EPIC-033S`),
    empty until a test seeds it."""
    return FakeHistoricalKlines()


@pytest.fixture
def scripts():
    registry = IndicatorScriptRegistry()
    registry.register("ema_20", Ema20Script)
    registry.register("rsi_14", Rsi14Script)
    return registry


def _deps(
    sources,
    threads,
    scripts,
    *,
    stream: IMarketStream | None = None,
    account=None,
    symbols=SYMBOLS,
    state=None,
) -> MarketDependencies:
    return MarketDependencies(
        stream=stream or FakeMarketStream(),
        candles={MarketType.SPOT: sources[0], MarketType.FUTURES_USD_M: sources[1]},
        history=sources[2],
        thread_manager=threads,
        scripts=scripts,
        script_params=lambda _key: None,
        account=account or FakeAccountSnapshot(status=CONNECTED),
        symbols=symbols,
        interval="1m",
        state=state,
    )


@pytest.fixture
def build(qapp, event_bus, feed, futures_feed, history, threads, scripts):
    made: list[MarketPresenter] = []

    def _build(**overrides) -> MarketPresenter:
        view = MarketView()
        presenter = MarketPresenter(
            view,
            presenter_container(event_bus),
            _deps((feed, futures_feed, history), threads, scripts, **overrides),
        )
        made.append(presenter)
        return presenter

    yield _build
    for presenter in made:
        presenter.shutdown()
