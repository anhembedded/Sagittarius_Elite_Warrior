"""`EPIC-029E` — a live Grid in the composed app, against the fake Binance server.

@details `create_app()` builds everything: the bots module with its use cases,
runner, executors and event router, and trading with the Spot adapters over
`python-binance`, the owner budget, `ExecuteOrderCommandHandler`, Emergency
Stop and the venue's emission path (`SpotUserDataStream` →
`VenueEventEmitter` → the bus → `BotEventRouter`). What is substituted, and
why:
- the network: `python-binance` points at `run_binance_fake_server()`, the
  venue's key pair comes from the environment, and every `get_loop` binding
  returns one loop this file owns (`BUG-075`, as the F9 test does);
- the fake has no websocket, so its executionReports are handed to the
  venue's own stream (`_deliver`), as the owner-budget test does;
- the bot's queue and pacer. The queue runs each task on the poster's thread,
  one at a time and in posting order (a task posted while one runs waits for
  it), so a journey is deterministic without a wait. The pacer delivers the
  reports before each turn: the stream's delivery within the spacing that
  `grid_start_sequence`'s known limit names. The thread queue and the
  monotonic pacer have their own unit tests;
- the session is seeded as enabled: the toggle would start the venue's
  websocket, which the fake does not speak (`EPIC-028S` §3). A restart
  enables by publishing the switch event the toggle publishes.

At each step the exchange's open orders are asserted against the bot's own
ladder, price for price and id for id.
"""

from __future__ import annotations

import asyncio
import json
import sys
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from binance.client import Client
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor_factory import (
    GridExecutorDeps,
    GridExecutorFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    decode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.create_bot import (
    CreateBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_pacer import (
    IOrderPacer,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_user_data_stream import (
    SpotUserDataStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.emergency_stop import (
    EmergencyStopCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_trading_scope import (
    VenueTradingScope,
    VenueTradingScopes,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
    TradingSwitchChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.support.binance_gateway.adapters.env_first_credentials_provider import (
    SPOT_ENV_API_KEY,
    SPOT_ENV_API_SECRET,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.kernel.app import App

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "sanity"))
from binance_fake_server import FakeServerUrls, run_binance_fake_server

_SPOT = TradingVenue.SPOT_TESTNET
_SYMBOL = "BTCUSDT"
_CONFIG_DIR = Path(__file__).resolve().parents[4] / "src" / "config"
#: The fake Spot account's balances before enabling: the user's own coins.
_BASELINE = {"USDT": Decimal(100000), "BTC": Decimal(10)}
#: Six levels 800 apart around the fake's 50,000: 49,600 is the nearest and
#: stays EMPTY, 48,000 and 48,800 buy, 50,400 to 52,000 sell. 2,000 USDT over
#: five orders is 400 a level, under the app's per-order limit.
_GRID = {
    "lower": "48000",
    "upper": "52000",
    "grid_count": "5",
    "spacing": "ARITHMETIC",
    "capital_quote": "2000",
    "stop_loss": "price:40000",
    "take_profit": "price:60000",
}
_GET_LOOP_BINDINGS = (
    "binance.base_client.get_loop",
    "binance.async_client.get_loop",
    "binance.ws.reconnecting_websocket.get_loop",
    "binance.ws.streams.get_loop",
    "binance.ws.threaded_stream.get_loop",
    "binance.ws.depthcache.get_loop",
)
S = BotLifecycleState


class _SerialQueue(IBotWorkQueue):
    """The bot's queue on the poster's thread: one task at a time, in order.
    A task that raises fails the test rather than being logged."""

    def __init__(self) -> None:
        self._tasks: deque[Callable[[], None]] = deque()
        self._running = False

    def post(self, task: Callable[[], None]) -> None:
        self._tasks.append(task)
        if self._running:
            return
        self._running = True
        try:
            while self._tasks:
                self._tasks.popleft()()
        finally:
            self._running = False

    def close(self) -> None:
        return None


class _DeliveringPacer(IOrderPacer):
    """Each turn first hands the stream what the exchange reported so far."""

    def __init__(self, deliver: Callable[[], None]) -> None:
        self._deliver = deliver

    def wait_turn(self) -> None:
        self._deliver()


@dataclass
class _App:
    """One boot of the composed app over the shared fake exchange."""

    engine: App
    urls: FakeServerUrls
    store: IBotStore
    scope: VenueTradingScope
    stream: SpotUserDataStream

    def deliver(self) -> None:
        for event in self.urls.spot_account.drain_user_data_events():
            if event["e"] == "executionReport":
                asyncio.run(self.stream._handle_message(event))

    def bot(self, bot_id: str) -> Bot:
        return self.store.load(BotId(bot_id)).bot

    def runtime(self, bot_id: str) -> GridRuntime:
        return decode_runtime(self.store.load(BotId(bot_id)).runtime)

    def move_price(self, price: int) -> None:
        self.urls.spot_account.set_last_price(_SYMBOL, Decimal(price))
        self.deliver()


def _config(tmp_path: Path) -> ConfigManager:
    user_json = tmp_path / "user_config.json"
    user_json.write_text(json.dumps({}))
    config = ConfigManager()
    config.load_json(str(_CONFIG_DIR / "app_config.json"))
    config.load_json(str(user_json), writable=True)
    config.load_dict(
        {
            "exchange.trading_venues": [_SPOT.value],
            "bots.state_dir": str(tmp_path / "bots"),
            "trading.bot_limits.min_order_spacing_ms": 0,
        }
    )
    return config


@dataclass
class _Exchange:
    urls: FakeServerUrls
    tmp_path: Path


@pytest.fixture
def exchange(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Exchange]:
    monkeypatch.setenv(SPOT_ENV_API_KEY, "fake-key")
    monkeypatch.setenv(SPOT_ENV_API_SECRET, "fake-secret")
    loop = asyncio.new_event_loop()
    with (
        run_binance_fake_server() as urls,
        patch.object(Client, "API_TESTNET_URL", urls.spot),
        ExitStack() as owned_loop,
    ):
        for binding in _GET_LOOP_BINDINGS:
            owned_loop.enter_context(patch(binding, lambda: loop))
        yield _Exchange(urls, tmp_path)
    loop.close()


@contextmanager
def _booted(exchange: _Exchange) -> Iterator[_App]:
    """The app with Spot Testnet on; its bots on the serial queue."""
    engine = create_app(_config(exchange.tmp_path))
    container = engine.context.container
    holder: list[_App] = []
    queue = _SerialQueue()
    pacer = _DeliveringPacer(lambda: holder[0].deliver())

    def executors(_container: IContainer) -> BotExecutors:
        deps = GridExecutorDeps(
            ports=container.resolve(IVenueTradingPorts),
            store=container.resolve(IBotStore),
            clock=container.resolve(IBotClock),
            caps=container.resolve(OwnerBudgetCaps),
            queues=lambda _name: queue,
            pacers=lambda _spacing: pacer,
        )
        return BotExecutors(GridExecutorFactory(deps))

    container.singleton(BotExecutors, executors)
    engine.boot()
    scope = container.resolve(VenueTradingScopes).get(_SPOT)
    stream = scope.ports.user_data_stream
    assert isinstance(stream, SpotUserDataStream)
    app = _App(engine, exchange.urls, container.resolve(IBotStore), scope, stream)
    holder.append(app)
    scope.session_state.enable(set(), spot_baseline_holdings=dict(_BASELINE))
    try:
        yield app
    finally:
        engine.stop()


def _resting(urls: FakeServerUrls) -> dict[str, tuple[str, Decimal]]:
    return {
        row["clientOrderId"]: (row["side"], Decimal(row["price"]))
        for row in urls.spot_account.open_orders(_SYMBOL)
    }


def _ladder(runtime: GridRuntime) -> dict[str, tuple[str, Decimal]]:
    return {o.client_order_id: (o.side.value, o.price) for o in runtime.open_orders}


def _sides_by_price(runtime: GridRuntime) -> dict[Decimal, str]:
    return {price: side for side, price in _ladder(runtime).values()}


def _started(app: _App) -> str:
    created = app.engine.dispatch(
        CreateBotCommand, CreateBotCommand("grid", "grid", _SPOT, _SYMBOL, _GRID)
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None
    started = app.engine.dispatch(StartBotCommand, StartBotCommand(created.bot_id))
    assert isinstance(started, BotCommandResult)
    assert started.accepted, started.message
    return created.bot_id


def test_a_grid_starts_cycles_replaces_a_cancel_and_halts_on_emergency_stop(
    exchange: _Exchange,
) -> None:
    with _booted(exchange) as app:
        bot_id = _started(app)

        assert app.bot(bot_id).state is S.RUNNING
        assert _resting(app.urls) == _ladder(app.runtime(bot_id))
        assert _sides_by_price(app.runtime(bot_id)) == {
            Decimal(48000): "BUY",
            Decimal(48800): "BUY",
            Decimal(50400): "SELL",
            Decimal(51200): "SELL",
            Decimal(52000): "SELL",
        }

        app.move_price(48700)  # the 48,800 buy fills; its sell goes one up

        assert _resting(app.urls) == _ladder(app.runtime(bot_id))
        assert _sides_by_price(app.runtime(bot_id))[Decimal(49600)] == "SELL"
        assert Decimal(48800) not in _sides_by_price(app.runtime(bot_id))

        app.move_price(49700)  # that sell fills: one cycle, the buy back

        runtime = app.runtime(bot_id)
        assert _resting(app.urls) == _ladder(runtime)
        assert _sides_by_price(runtime)[Decimal(48800)] == "BUY"
        assert runtime.completed_cycles == 1
        assert runtime.realised_profit > 0

        cancelled = next(
            oid
            for oid, (_side, price) in _ladder(runtime).items()
            if price == Decimal(48000)
        )
        _cancel_from_outside(app, cancelled)

        runtime = app.runtime(bot_id)
        assert _resting(app.urls) == _ladder(runtime)
        assert _sides_by_price(runtime)[Decimal(48000)] == "BUY"
        assert cancelled not in _ladder(runtime)

        app.engine.dispatch(EmergencyStopCommand, EmergencyStopCommand(venue=_SPOT))
        app.deliver()

        assert app.bot(bot_id).state is S.HALTED
        assert app.runtime(bot_id).reason is GridReason.SWITCH_OFF
        assert _resting(app.urls) == {}


def _cancel_from_outside(app: _App, client_order_id: str) -> None:
    """The user cancels one of the bot's orders on the exchange's website."""
    app.scope.ports.client_factory.create(OrderSubmissionMode.LIVE).cancel_order(
        _SYMBOL, client_order_id
    )
    app.deliver()


def test_a_restart_reconciles_a_fill_missed_while_closed_without_a_duplicate(
    exchange: _Exchange,
) -> None:
    """The app closes with the ladder resting; the 48,800 buy fills while it
    is closed, so no stream hears it. On the next boot the bot is RECOVERING
    and places nothing; trading on reconciles it from the exchange's history:
    the fill is counted, its sell placed once, and every level holds at most
    one order."""
    with _booted(exchange) as first:
        bot_id = _started(first)
        bought_before = first.runtime(bot_id).inventory

    exchange.urls.spot_account.set_last_price(_SYMBOL, Decimal(48700))
    exchange.urls.spot_account.drain_user_data_events()  # nobody was listening

    with _booted(exchange) as second:
        assert second.bot(bot_id).state is S.RECOVERING
        posts_before = len(_resting(second.urls))

        second.engine.event_bus.emit(
            TradingSwitchChangedEvent(True, TradingSwitchCause.ENABLED, venue=_SPOT)
        )

        runtime = second.runtime(bot_id)
        assert second.bot(bot_id).state is S.RUNNING
        assert _resting(second.urls) == _ladder(runtime)
        assert len(_resting(second.urls)) == posts_before + 1
        prices = [price for _side, price in _resting(second.urls).values()]
        assert len(prices) == len(set(prices))
        assert _sides_by_price(runtime)[Decimal(49600)] == "SELL"
        assert runtime.inventory > bought_before
