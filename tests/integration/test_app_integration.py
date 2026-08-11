from unittest.mock import patch

import pytest

from Sagittarius_Elite_Warrior.src.application.use_cases.stream.start_live_stream import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.stream.stop_live_stream import (
    StopLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.binance_bot_module import BinanceBotModule
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from sagittarius_engine import App
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.infrastructure.container.std_container import StdLibContainer
from sagittarius_engine.infrastructure.event_bus.memory_event_bus import MemoryEventBus
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_event_bus import IEventBus


@pytest.fixture
def app_instance():
    container = StdLibContainer()
    event_bus = MemoryEventBus()
    config_manager = ConfigManager()

    container.singleton(IEventBus, event_bus)
    container.singleton(IConfig, config_manager)

    app = App(container, event_bus)
    app.use(BinanceBotModule())

    return app


def test_app_boot_and_stream_use_case(app_instance):
    """
    Tests the full lifecycle: Booting the app, dispatching the stream command,
    and ensuring the engine context is available and no DI errors occur.
    """
    app = app_instance

    with (
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.BinanceSocketManager"
        ),
    ):
        # Boot the engine (this triggers HostedService start() which sets the context)
        app.boot()

        # Dispatch StartLiveStreamCommand
        cmd = StartLiveStreamCommand(symbols=["BTCUSDT"], interval=TimeFrame("1m"))
        response = app.dispatch(StartLiveStreamCommand, cmd)

        assert response.success is True

        # Give the background thread's asyncio loop a moment to start the coroutine
        # so it doesn't get cancelled before being awaited (which causes a warning)
        import time

        time.sleep(0.1)

        # Stop the stream
        stop_cmd = StopLiveStreamCommand()
        stop_response = app.dispatch(StopLiveStreamCommand, stop_cmd)

        assert stop_response.success is True

        app.stop()
