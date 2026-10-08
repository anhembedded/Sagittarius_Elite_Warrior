"""`EPIC-029B` — the bots module registered on a real container, shared by the wiring files.

A fake of each foreign port (`trading`, `market_data`), a real `StdLibContainer`, a
real bus and the real `BotsModule.register()`; `EPIC-035A` adds the verified fake
market stream and ticker the price watch runs on, so nothing opens a socket or a
thread of its own.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from Sagittarius_Elite_Warrior.src.core.contracts.i_close_objections import (
    ICloseObjections,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.core.contracts.testing.recording_notifier import (
    RecordingNotifier,
)
from Sagittarius_Elite_Warrior.src.infrastructure.engine_adapters.event_publisher_adapter import (
    EngineEventPublisher,
)
from Sagittarius_Elite_Warrior.src.infrastructure.instance.instance_access import (
    InstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_ticker import (
    IBotTicker,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_ticker import (
    FakeBotTicker,
)
from Sagittarius_Elite_Warrior.src.modules.bots.module import BotsModule
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_historical_klines import (
    IHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_repository import (
    IMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_repository import (
    FakeMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_accounts import (
    IVenueAccounts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    DEFAULT_OWNER_BUDGET_CAPS,
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_accounts import (
    FakeVenueAccounts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_trading_ports import (
    FakeVenueTradingPorts,
    fake_venue_ports,
)
from Sagittarius_Elite_Warrior.src.shell.close_objections import CloseObjections
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.dict_config import DictConfig
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig

RUN_STARTED = datetime(2026, 10, 8, 9, tzinfo=UTC)
GRID_CONFIG = {
    "lower": "60000",
    "upper": "70000",
    "grid_count": "4",
    "spacing": "ARITHMETIC",
    "capital_quote": "1000",
    "stop_loss": "price:50000",
    "take_profit": "price:80000",
}


def registered(
    state_dir: Path, instance: IInstanceAccess | None = None
) -> tuple[BotsModule, SimpleNamespace]:
    """The module on a real container; `instance` is this copy's access
    (`EPIC-035H`), writable when not given."""
    container = StdLibContainer()
    container.singleton(
        IInstanceAccess,
        instance if instance is not None else InstanceAccess.unguarded(),
    )
    container.singleton(IConfig, DictConfig({"bots.state_dir": str(state_dir)}))
    container.singleton(
        IVenueTradingPorts,
        FakeVenueTradingPorts(fake_venue_ports(TradingVenue.SPOT_TESTNET)),
    )
    container.singleton(OwnerBudgetCaps, DEFAULT_OWNER_BUDGET_CAPS)
    container.singleton(IVenueAccounts, FakeVenueAccounts())
    container.singleton(IHistoricalKlines, FakeHistoricalKlines())
    container.singleton(IMarketDataRepository, FakeMarketDataRepository())
    streams = FakeMarketStream()
    container.singleton(
        IMarketDataSources,
        FakeMarketDataSources().serving(
            FakeMarketDataSources.ports(
                TradingVenue.SPOT_TESTNET.market_data_venue, stream=streams
            )
        ),
    )
    ticker = FakeBotTicker()
    container.singleton(IBotTicker, ticker)
    event_bus = MemoryEventBus()
    container.singleton(IEventPublisher, EngineEventPublisher(event_bus))
    container.singleton(ICloseObjections, CloseObjections())
    container.singleton(INotifier, RecordingNotifier())
    context = SimpleNamespace(
        container=container, event_bus=event_bus, streams=streams, ticker=ticker
    )
    module = BotsModule()
    module.register(context)
    return module, context


def bot_threads() -> list[str]:
    return [
        t.name for t in threading.enumerate() if t.name == "bot-abc123" and t.is_alive()
    ]
