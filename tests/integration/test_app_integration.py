import logging
from unittest.mock import patch

import pytest
from Sagittarius_Elite_Warrior.src.binance_bot_module import BinanceBotModule
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.start_live_stream import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.stream.stop_live_stream import (
    StopLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.shell.module_registration import register_modules
from Sagittarius_Elite_Warrior.src.shell.modules import MODULES
from sagittarius_engine import App
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus


@pytest.fixture
def app_instance():
    """A booted app wired the way `shell/composition_root.py` wires the real one.

    `EPIC-025` PR 0.4a: this fixture used to register `BinanceBotModule` alone,
    which was a faithful copy of the boot sequence right up until the sequence
    changed — the stream commands moved into `MarketDataModule`, and a test
    whose whole point is "no DI errors occur on a real boot" started resolving
    an unbound command and failing with `Any cannot be instantiated`. It failed
    for the right reason: the app it built was not the app that ships.

    So it now calls `register_modules(app, MODULES)`, the same function the
    composition root calls, rather than naming modules itself. The next context
    to move out of `binance_bot_module.py` needs no edit here, and if one is
    ever missing from `MODULES` this test fails instead of passing against a
    smaller app than the user runs.
    """
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    config_manager = ConfigManager()

    container.singleton(IEventBus, event_bus)
    container.singleton(IConfig, config_manager)

    app = App(container, event_bus)
    app.use(BinanceBotModule())
    register_modules(app, MODULES)

    yield app
    try:
        app.stop()
    except Exception:
        logging.getLogger(__name__).exception("App fixture teardown shutdown failed")


def test_app_boot_and_stream_use_case(app_instance):
    """
    Tests the full lifecycle: Booting the app, dispatching the stream command,
    and ensuring the engine context is available and no DI errors occur.
    """
    app = app_instance

    with (
        patch(
            "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.modules.market_data.adapters.binance.binance_websocket_service.BinanceSocketManager"
        ),
    ):
        # Boot the engine (this triggers HostedService start() which sets the context)
        app.boot()

        # Dispatch StartLiveStreamCommand
        cmd = StartLiveStreamCommand(
            owner="test", symbols=["BTCUSDT"], interval=TimeFrame("1m")
        )
        response = app.dispatch(StartLiveStreamCommand, cmd)

        assert response.success is True

        # Give the background thread's asyncio loop a moment to start the coroutine
        # so it doesn't get cancelled before being awaited (which causes a warning)
        import time

        time.sleep(0.1)

        # Stop the stream
        stop_cmd = StopLiveStreamCommand(owner="test")
        stop_response = app.dispatch(StopLiveStreamCommand, stop_cmd)

        assert stop_response.success is True

        app.stop()
