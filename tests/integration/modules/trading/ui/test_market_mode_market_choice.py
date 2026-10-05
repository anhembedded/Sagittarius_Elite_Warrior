"""`EPIC-033Q` — Market → Futures reloads the open charts from the Futures
store, through the real candle feed the mode builds (`MarketDataCandleFeed`)
over in-memory market-data ports; the Spot candles never come back."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sync import (
    FakeMarketDataSync,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_account_snapshot import (
    FakeAccountSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    SHOW_FUTURES,
    market_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_dependencies import (
    MARKETS,
    MarketDependencies,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_presenter import (
    WATCHLIST_STREAM_OWNER,
    MarketPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_screen import (
    MARKET_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_view import (
    MarketView,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.market.market_fixtures import (
    presenter_container,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

_SPOT_CLOSE = 105.0
_FUTURES_CLOSE = 205.0


class _InlineThreadManager(IThreadManager):
    """Runs each task as it is submitted: the load lands before `submit`
    returns, so the test waits on nothing."""

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        future.set_result(task(*args, **kwargs))
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None


@pytest.fixture
def mode(qapp):
    history = FakeHistoricalKlines()
    for market, close in (
        (MarketType.SPOT, _SPOT_CLOSE),
        (MarketType.FUTURES_USD_M, _FUTURES_CLOSE),
    ):
        history.seed(
            [candle("BTCUSDT", minute, close_price=close) for minute in range(30)],
            market,
        )
    stream = FakeMarketStream()
    sync = FakeMarketDataSync()
    dependencies = MarketDependencies(
        stream=stream,
        candles={
            market: MarketDataCandleFeed(sync, history, stream, market)
            for market in MARKETS
        },
        thread_manager=_InlineThreadManager(),
        scripts=IndicatorScriptRegistry(),
        script_params=lambda _key: None,
        account=FakeAccountSnapshot(),
        symbols=("BTCUSDT",),
        interval="1m",
    )
    presenter = MarketPresenter(
        MarketView(), presenter_container(MemoryEventBus()), dependencies
    )
    owner = QObject()
    registry = bound_actions(
        owner, market_commands(MARKET_ROUTE), presenter.bind_commands
    )
    yield presenter, registry, history, stream
    presenter.shutdown()
    owner.deleteLater()


def _drawn_closes(presenter: MarketPresenter) -> set[float]:
    card = presenter.charts["BTCUSDT"].chart
    return {close for *_ohlc, close in card._raw_history}


def test_futures_reloads_the_open_chart_from_the_futures_store(mode):
    presenter, registry, history, stream = mode
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    assert _drawn_closes(presenter) == {_SPOT_CLOSE}

    registry.action(SHOW_FUTURES).trigger()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert _drawn_closes(presenter) == {_FUTURES_CLOSE}
    assert history.reads[-1].market is MarketType.FUTURES_USD_M
    for owner in (WATCHLIST_STREAM_OWNER, "market.BTCUSDT"):
        held = stream.held_by(owner)
        assert held is not None
        assert held.market_type is MarketType.FUTURES_USD_M
