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
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.event_handlers.market_tick_event_handler import (
    MarketTickEventHandler,
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


def _tick_handler_subscriptions(app) -> list:
    """Bus subscribers to `MarketTickEvent` that are a `MarketTickEventHandler`.

    Not *every* subscriber to that event, deliberately. `MarketTickFeed`
    (`presentation/ui/common/`) legitimately subscribes too — it is the one Qt
    normaliser both live screens read the raw tick through — so a running app
    with a screen open has more than one, and a total count would be asserting
    something false about it (`ONBOARDING` §8 trap 3: the count that breaks when
    nothing is wrong). What must be exactly one is the subscriber that *drives
    the armed strategy*, because that is the one whose duplication submits two
    orders for one signal.
    """
    subscribed = app.event_bus.subscriptions().get(MarketTickEvent.__name__, ())
    return [
        handler
        for handler in subscribed
        if isinstance(getattr(handler, "__self__", None), MarketTickEventHandler)
    ]


def test_a_real_boot_leaves_exactly_one_tick_handler_on_the_strategy_path(
    app_instance,
):
    """`EPIC-025` PR 2.1c-2 — the claim no unit test can make.

    That pull request moved the `MarketTickEvent` subscription out of
    `binance_bot_module.boot()` and into `StrategyModule.boot()`. Both modules
    boot on this fixture, which registers the shipping `MODULES` list through
    the same `register_modules()` the composition root calls, so this is where
    the two ways of getting it wrong are visible:

      · **zero** — the subscription was removed from one `boot()` and never
        added to the other, which is the app quietly not trading while the UI
        says trading is ON (`EPIC-022B`'s exact symptom, and `BUG-126`'s shape:
        a handler nobody subscribes reaches nobody);
      · **two** — it was added without removing the old one, so every candle
        runs the armed strategy twice and one signal tries to submit two
        orders.

    A unit test of `StrategyModule.boot()` cannot see either, because it boots
    that module alone. `tests/unit/modules/strategy/test_module_tick_
    subscription.py` owns the wiring itself; this owns "on the app that ships,
    once".

    No network: `app.boot()` here starts hosted services, and the live stream
    connects only when `StartLiveStreamCommand` asks (see
    `MarketDataModule.boot()`).
    """
    app = app_instance

    app.boot()

    handlers = _tick_handler_subscriptions(app)

    assert len(handlers) == 1, (
        f"{len(handlers)} MarketTickEventHandler(s) subscribed to "
        f"{MarketTickEvent.__name__} on a real boot — exactly one module must "
        f"own the live tick path (EPIC-025 PR 2.1c-2). Got: {handlers!r}"
    )
