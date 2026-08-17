"""
Layer 1 sanity test (mirrors test_bootstrapper_di_sanity.py): boots the app
for real (no mocked dispatch, no UI) and verifies every piece of DI wiring
the Backtest Screen (BOT-022/055/056) actually depends on resolves —
catches a wiring regression (a handler/script/strategy silently dropped
from binance_bot_module.py) before any Backtest unit test even starts.
Meant to run in well under a second.
"""

import os
from unittest.mock import patch

import pytest
from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest.command import (
    RunStaticBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest.handler import (
    RunStaticBacktestCommandHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_backtest_range_coverage import (
    GetBacktestRangeCoverageQuery,
    GetBacktestRangeCoverageQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.handler import (
    GetHistoricalKlinesQueryHandler,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.handler import (
    SyncMarketDataCommandHandler,
)
from Sagittarius_Elite_Warrior.src.main import create_app
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

#: Every BackTestPresenter dispatch call — the run itself (BOT-022), the
#: chart kline fetch (BOT-056), and the "Đồng bộ ngay" sync (BOT-059) —
#: goes through exactly these registrations today.
_BACKTEST_COMMANDS = {
    RunStaticBacktestCommand: RunStaticBacktestCommandHandler,
    GetBacktestRangeCoverageQuery: GetBacktestRangeCoverageQueryHandler,
    GetHistoricalKlinesQuery: GetHistoricalKlinesQueryHandler,
    SyncMarketDataCommand: SyncMarketDataCommandHandler,
}


@pytest.fixture
def booted_app():
    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_manager.load_json(os.path.join(base_dir, "src", "config", "app_config.json"))
    config_manager.load_json(
        os.path.join(base_dir, "src", "config", "user_config.json")
    )

    app = create_app(config_manager)

    # Boot for real (no dispatch mocking) — only the WebSocket client/socket
    # manager are patched, since HostedService.start() would otherwise try
    # to touch the network (same as test_bootstrapper_di_sanity.py).
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


@pytest.mark.parametrize(
    "command_class,expected_handler",
    list(_BACKTEST_COMMANDS.items()),
    ids=lambda cls: cls.__name__,
)
def test_backtest_command_resolves_to_its_handler(
    booted_app, command_class, expected_handler
):
    """`IDispatcher.dispatch(command_class, ...)` resolves via
    `container.resolve(command_class)` — mirrors the exact lookup key
    `Dispatcher.dispatch()` uses (`sagittarius_engine/kernel/dispatcher.py`),
    not a guess at how DI registration works."""
    handler = booted_app.context.container.resolve(command_class)
    assert isinstance(handler, expected_handler)


def test_strategy_registry_has_the_default_backtest_strategy(booted_app):
    """`BackTestViewModel.set_strategy_options()`'s dropdown, and the "Chưa
    có chiến lược nào được đăng ký" guard in `_build_run_config`, both
    depend on at least one strategy being registered."""
    registry = booted_app.context.container.resolve(StrategyRegistry)
    assert "ema_crossover" in registry.available()


def test_strategy_registry_has_multi_ema_trend_follower(booted_app):
    """BOT-051 — pinned separately so an accidental un-registration in
    `binance_bot_module.py` shows up here instead of only as a missing
    dropdown option a user has to notice by eye."""
    registry = booted_app.context.container.resolve(StrategyRegistry)
    assert "multi_ema_trend_follower" in registry.available()


def test_indicator_script_registry_resolves_for_the_backtest_screen(booted_app):
    """BOT-064 — BackTestPresenter now resolves `IndicatorScriptRegistry`
    too (for the "Chỉ báo tham khảo" picker), same registry Dev Board
    already depends on; at least the shipped defaults must be there."""
    registry = booted_app.context.container.resolve(IndicatorScriptRegistry)
    assert "ema_20" in registry.available()
