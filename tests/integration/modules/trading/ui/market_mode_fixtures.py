"""The Market mode built for integration tests (`EPIC-033Q`, `EPIC-033S`):
the real presenter, view and `MarketDataCandleFeed`s over in-memory
market-data ports, its commands as the window builds them, and a thread
manager that runs each task as it is submitted."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
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
    market_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_dependencies import (
    MARKETS,
    MarketDependencies,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_presenter import (
    MarketPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_screen import (
    MARKET_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_view import (
    MarketView,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.market.market_fixtures import (
    presenter_container,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.action_registry import (
    ActionRegistry,
)
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager


class InlineThreadManager(IThreadManager):
    """Runs each task as it is submitted: a load lands before `submit`
    returns, so a test waits on nothing."""

    def submit(
        self, task: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> concurrent.futures.Future[Any]:
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        future.set_result(task(*args, **kwargs))
        return future

    def shutdown(self, wait: bool = True) -> None:
        return None


@dataclass(frozen=True)
class MarketMode:
    presenter: MarketPresenter
    actions: ActionRegistry
    stream: FakeMarketStream


@contextmanager
def market_mode(history: FakeHistoricalKlines) -> Iterator[MarketMode]:
    """The mode tracking BTCUSDT over `history`, shut down on exit."""
    stream = FakeMarketStream()
    sync = FakeMarketDataSync()
    dependencies = MarketDependencies(
        stream=stream,
        candles={
            market: MarketDataCandleFeed(sync, history, stream, market)
            for market in MARKETS
        },
        history=history,
        venue=MarketDataVenue.MAINNET_PUBLIC,
        thread_manager=InlineThreadManager(),
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
    actions = bound_actions(
        owner, market_commands(MARKET_ROUTE), presenter.bind_commands
    )
    try:
        yield MarketMode(presenter, actions, stream)
    finally:
        presenter.shutdown()
        owner.deleteLater()
