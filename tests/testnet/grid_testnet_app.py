"""The composed app on Spot Testnet, as `EPIC-029H`'s two tests use it.

`test_grid_bot_round_trip.py` drives one Grid bot through the bots use cases;
`test_spot_rate_limits.py` reads the owner-budget caps the app resolves. Both
build the app from the shipped `app_config.json` with only Spot Testnet on,
so the keys and the caps are the ones a person's run uses.

`composed_on_spot_testnet` boots it and reaches the venue's trading client;
`enable_trading` then turns trading on through `EnableTradingCommand`, which
starts the user-data websocket. The composition is the one place the client
is reached, so the fake exchange proves it in CI
(`tests/integration/modules/bots/test_spot_testnet_boot_on_the_fake_exchange.py`)
before a person's run depends on it. The enabling is not run there: the fake
server does not speak the websocket (the same limit as
`test_spot_desk_against_fake_server.py`).

The round trip's support lives here, beside the app it reads:

- `stream_latency_s` proves the venue's user-data stream live before a bot
  starts (the PR #339 review). An untagged LIMIT BUY 20% under the price, at
  twice the minimum notional, is placed and cancelled until its cancel comes
  back as an `OrderEndedEvent`; cancel to event is the stream latency
  `EPIC-029E` handed to 029H.
- `wait_for_state` fails at once, with the runtime's reason, when the bot
  halts or errs instead of reaching the state waited for.
- `clean_up` stops a bot still running, selling its base, before cancelling
  what is left: a cancel heard while RUNNING is laid again.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    decode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.session.enable_trading.command import (
    EnableTradingCommand,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.enable_trading_result import (
    EnableTradingResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.order_ended_event import (
    OrderEndedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.testnet.round_trips import wait_until
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.kernel.app import App

SPOT = TradingVenue.SPOT_TESTNET
SYMBOL = "BTCUSDT"
_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_DIR = _ROOT / "src" / "config"
_REPORTS = _ROOT / "logs" / "testnet"
#: The stream probe: 20% under the price, inside Binance's price bands, far
#: from any fill.
_PROBE_DISCOUNT = Decimal("0.8")
_PROBE_ATTEMPTS = 3
S = BotLifecycleState
_FAILED = (S.HALTED, S.ERROR)


@dataclass
class GridTestnetApp:
    engine: App
    store: IBotStore
    client: ITradingClient
    ended: set[str] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def on_ended(self, event: OrderEndedEvent) -> None:
        with self.lock:
            self.ended.add(event.order.client_order_id)

    def heard_end(self, client_order_id: str) -> bool:
        with self.lock:
            return client_order_id in self.ended

    def runtime(self, bot_id: str) -> GridRuntime:
        return decode_runtime(self.store.load(BotId(bot_id)).runtime)

    def state(self, bot_id: str) -> BotLifecycleState:
        return self.store.load(BotId(bot_id)).bot.state

    def tagged_open(self, bot_id: str) -> dict[str, Decimal | None]:
        return {
            order.client_order_id: order.price
            for order in self.client.get_open_orders(SYMBOL)
            if tag_of(order.client_order_id) == bot_id
        }


def spot_testnet_config(tmp_path: Path) -> ConfigManager:
    user_json = tmp_path / "user_config.json"
    user_json.write_text(json.dumps({}))
    config = ConfigManager()
    config.load_json(str(_CONFIG_DIR / "app_config.json"))
    config.load_json(str(user_json), writable=True)
    config.load_dict(
        {
            "exchange.trading_venues": [SPOT.value],
            "bots.state_dir": str(tmp_path / "bots"),
        }
    )
    return config


@contextmanager
def composed_on_spot_testnet(config: ConfigManager) -> Iterator[GridTestnetApp]:
    """The app booted from `config` with the venue's live trading client and
    its order ends heard; stopped on exit. Trading is still off."""
    engine = create_app(config)
    engine.boot()
    try:
        container = engine.context.container
        # The trading client is a venue context's, not a published port.
        venue = container.resolve(IVenueContexts).get(SPOT)
        app = GridTestnetApp(
            engine,
            container.resolve(IBotStore),
            venue.client_factory.create(OrderSubmissionMode.LIVE),
        )
        engine.event_bus.on(OrderEndedEvent, app.on_ended)
        yield app
    finally:
        engine.stop()


def enable_trading(app: GridTestnetApp) -> None:
    enabled = app.engine.dispatch(
        EnableTradingCommand, EnableTradingCommand(venue=SPOT)
    )
    assert isinstance(enabled, EnableTradingResult)
    assert enabled.enabled, f"trading did not turn on: {enabled.block_reason}"


def write_report(name: str, content: dict[str, Any]) -> None:
    _REPORTS.mkdir(parents=True, exist_ok=True)
    (_REPORTS / name).write_text(json.dumps(content, indent=2, default=str))


def round_to_step(value: Decimal, step: Decimal, rounding: str) -> Decimal:
    return (value / step).to_integral_value(rounding) * step


def stream_latency_s(
    app: GridTestnetApp, terms: ExchangeTerms, price: Decimal
) -> float:
    """Places and cancels an untagged far-away LIMIT BUY until its cancel comes
    back on the stream; returns the cancel-to-event latency of the one heard."""
    probe_price = round_to_step(price * _PROBE_DISCOUNT, terms.tick_size, ROUND_FLOOR)
    quantity = round_to_step(
        terms.min_notional * 2 / probe_price, terms.step_size, ROUND_CEILING
    )
    for attempt in range(1, _PROBE_ATTEMPTS + 1):
        probe = Order(
            client_order_id=generate_client_order_id(),
            symbol=SYMBOL,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=probe_price,
            time_in_force=TimeInForce.GTC,
        )
        app.client.place_order(probe)
        app.client.cancel_order(SYMBOL, probe.client_order_id)
        cancelled_at = time.monotonic()
        try:
            wait_until(
                f"the probe's cancel on the stream (attempt {attempt})",
                lambda probe_id=probe.client_order_id: app.heard_end(probe_id),
            )
        except TimeoutError:
            if attempt == _PROBE_ATTEMPTS:
                raise
            continue
        return time.monotonic() - cancelled_at
    raise AssertionError("unreachable")


def wait_for_state(app: GridTestnetApp, bot_id: str, wanted: BotLifecycleState) -> None:
    """Waits for `wanted`; fails at once, with the runtime's reason, when the
    bot halts or errs instead."""

    def reached() -> bool:
        state = app.state(bot_id)
        if state in _FAILED and wanted not in _FAILED:
            runtime = app.runtime(bot_id)
            raise AssertionError(
                f"the bot went {state.value} waiting for {wanted.value}: "
                f"{runtime.reason} {runtime.reason_detail}"
            )
        return state is wanted

    wait_until(f"the bot {wanted.value}", reached)


def clean_up(app: GridTestnetApp, bot_id: str) -> None:
    """Stops a bot still running (selling its base), then cancels what is
    left. A cancel heard while RUNNING would be laid again. A refused Stop
    (a bot that never started) is not waited on."""
    if app.state(bot_id) is not S.STOPPED:
        stopped = app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, BaseHandling.SELL_AT_MARKET)
        )
        if isinstance(stopped, BotCommandResult) and stopped.accepted:
            wait_until(
                "the bot stopped in clean-up", lambda: app.state(bot_id) is S.STOPPED
            )
    for client_order_id in app.tagged_open(bot_id):
        app.client.cancel_order(SYMBOL, client_order_id)
