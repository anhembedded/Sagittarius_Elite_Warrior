"""
Layer 1 sanity test (BOT-015): boots the app through the exact same create_app()
factory app_bootstrapper.py uses in production (no mocked dispatch, no UI) and
verifies every core engine interface resolves. Meant to run in well under a
second and catch DI wiring regressions before any behavior test even starts —
e.g. a module forgetting to register an extension it depends on.
"""

import os
from unittest.mock import patch

import pytest

from Sagittarius_Elite_Warrior.src.main import create_app
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_event_bus import IEventBus
from sagittarius_engine.interfaces.i_task_manager import ITaskManager
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

_CORE_INTERFACES = [IDispatcher, IEventBus, IThreadManager, IConfig, ITaskManager]


@pytest.fixture
def booted_app():
    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_manager.load_json(os.path.join(base_dir, "src", "config", "app_config.json"))
    config_manager.load_json(
        os.path.join(base_dir, "src", "config", "user_config.json")
    )

    app = create_app(config_manager)

    # Boot for real (no dispatch mocking) — only the WebSocket client/socket manager
    # are patched, since HostedService.start() would otherwise try to touch the network.
    with (
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.BinanceSocketManager"
        ),
    ):
        app.boot()
        yield app
        app.stop()


@pytest.mark.parametrize("interface", _CORE_INTERFACES, ids=lambda i: i.__name__)
def test_core_interface_resolves_after_boot(booted_app, interface):
    """Every core interface the presentation/application layers depend on must resolve."""
    instance = booted_app.context.container.resolve(interface)
    assert instance is not None
