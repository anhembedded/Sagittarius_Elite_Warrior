"""`EPIC-029H` — one Grid bot on the real Spot Testnet, through the composed app.

The fake exchange proves the ladder's logic (`test_grid_bot_against_fake_server.py`);
only the real venue proves acceptance, the cancel payload (ADR D8), the order
rate and the user-data stream. So this test boots the app as a person runs
it, with Spot Testnet enabled and the keys read by the app itself, and turns
trading on through `EnableTradingCommand`, which *spawns* the venue's
user-data websocket.

**The stream is proven live before the bot starts** (the PR #339 review):
the opening buy's fill must arrive on the stream within the pacer's spacing
or the SELL levels are refused and the bot halts (`grid_start_sequence`'s
known limit). So a probe — an untagged LIMIT BUY 20% under the price, at
twice the minimum notional, placed and cancelled — repeats until its cancel
comes back as an `OrderEndedEvent`. Its latency, cancel to event, is the
stream's latency `EPIC-029E` handed to this task; it is recorded.

Then one narrow Grid is driven with the bots use cases:

1. **Start**: every level the bot's runtime holds is RESTING on the exchange,
   with the bot's tag, and nothing else of the bot's is.
2. **A cancel from outside** (the user, on Binance's site): the bot hears it
   on the stream and lays the same level again under a new id.
3. **Stop**, selling the base: no order carrying the bot's tag stays open.

Narrow on purpose: four levels 5% either side of the last price, every order
at four times the minimum notional, so nothing should fill while it runs.
A wait for a state fails at once, with the runtime's reason, when the bot
halts or errs instead.

**Clean-up** stops a bot still running, selling its base, before cancelling
what is left: a cancel heard while RUNNING is laid again, which is step 2's
own behaviour. A clean-up failure never hides the test's own.

What it measured goes to `logs/testnet/spot_grid_round_trip.json`. A second
test reads the venue's `exchangeInfo.rateLimits` and the symbol's
`MAX_NUM_ORDERS`, works out how many owner budgets at the O1 caps fit one
account, burst and open orders both, and writes it to
`logs/testnet/spot_rate_limits.json` (the build container cannot reach
Binance, `EPIC-029A`).

Opt-in only, behind this tree's two gates (`conftest.py`).
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
    PlannerMarket,
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
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.binance.spot.spot_session_factory import (
    SpotSessionFactory,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerBudgetCaps,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.time_in_force import (
    TimeInForce,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.testnet.round_trips import wait_until
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.kernel.app import App

logger = logging.getLogger("App.Tests.Testnet")

_SPOT = TradingVenue.SPOT_TESTNET
_SYMBOL = "BTCUSDT"
_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_DIR = _ROOT / "src" / "config"
_REPORTS = _ROOT / "logs" / "testnet"
#: Four levels (three gaps) 5% either side of the last price.
_HALF_RANGE = Decimal("0.05")
_GRID_COUNT = 3
#: Every grid order at four times the venue's minimum notional.
_NOTIONAL_MARGIN = 4
#: The stream probe: 20% under the price, inside Binance's price bands, far
#: from any fill.
_PROBE_DISCOUNT = Decimal("0.8")
_PROBE_ATTEMPTS = 3
S = BotLifecycleState
_FAILED = (S.HALTED, S.ERROR)
_WINDOW_S = {"SECOND": 1, "MINUTE": 60, "HOUR": 3600, "DAY": 86400}


@dataclass
class _Booted:
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
            for order in self.client.get_open_orders(_SYMBOL)
            if tag_of(order.client_order_id) == bot_id
        }


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
        }
    )
    return config


@pytest.fixture
def booted(
    spot_testnet_credentials: ExchangeCredentials, tmp_path: Path
) -> Iterator[_Booted]:
    """The app booted with Spot Testnet on and trading enabled. The credential
    fixture is the gate; the app resolves the keys itself."""
    engine = create_app(_config(tmp_path))
    engine.boot()
    try:
        container = engine.context.container
        ports = container.resolve(IVenueTradingPorts).get(_SPOT)
        app = _Booted(
            engine,
            container.resolve(IBotStore),
            ports.client_factory.create(OrderSubmissionMode.LIVE),
        )
        engine.event_bus.on(OrderEndedEvent, app.on_ended)
        enabled = engine.dispatch(
            EnableTradingCommand, EnableTradingCommand(venue=_SPOT)
        )
        assert isinstance(enabled, EnableTradingResult)
        assert enabled.enabled, f"trading did not turn on: {enabled.block_reason}"
        yield app
    finally:
        engine.stop()


def _terms_and_price(app: _Booted) -> tuple[ExchangeTerms, Decimal]:
    market = app.engine.dispatch(
        GetPlannerMarketQuery, GetPlannerMarketQuery(_SPOT, _SYMBOL)
    )
    assert isinstance(market, PlannerMarket)
    assert market.terms is not None and market.market is not None, market.problem
    return market.terms, market.market.last_price


def _round(value: Decimal, step: Decimal, rounding: str) -> Decimal:
    return (value / step).to_integral_value(rounding) * step


def _stream_latency_s(app: _Booted, terms: ExchangeTerms, price: Decimal) -> float:
    """Places and cancels an untagged far-away LIMIT BUY until its cancel comes
    back on the stream; returns the cancel-to-event latency of the one heard."""
    probe_price = _round(price * _PROBE_DISCOUNT, terms.tick_size, ROUND_FLOOR)
    quantity = _round(
        terms.min_notional * 2 / probe_price, terms.step_size, ROUND_CEILING
    )
    for attempt in range(1, _PROBE_ATTEMPTS + 1):
        probe = Order(
            client_order_id=generate_client_order_id(),
            symbol=_SYMBOL,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=probe_price,
            time_in_force=TimeInForce.GTC,
        )
        app.client.place_order(probe)
        app.client.cancel_order(_SYMBOL, probe.client_order_id)
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


def _wait_for_state(app: _Booted, bot_id: str, wanted: BotLifecycleState) -> None:
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


def _grid_config(terms: ExchangeTerms, price: Decimal) -> dict[str, str]:
    lower = _round(price * (1 - _HALF_RANGE), terms.tick_size, ROUND_FLOOR)
    upper = _round(price * (1 + _HALF_RANGE), terms.tick_size, ROUND_CEILING)
    capital = terms.min_notional * _NOTIONAL_MARGIN * (_GRID_COUNT + 1)
    return {
        "lower": str(lower),
        "upper": str(upper),
        "grid_count": str(_GRID_COUNT),
        "spacing": "ARITHMETIC",
        "capital_quote": str(capital),
        "stop_loss": "off",
        "take_profit": "off",
    }


def _command(app: _Booted, command: Any) -> BotCommandResult:
    result = app.engine.dispatch(type(command), command)
    assert isinstance(result, BotCommandResult)
    assert result.accepted, result.message
    return result


def _ladder(runtime: GridRuntime) -> dict[str, Decimal | None]:
    return {order.client_order_id: order.price for order in runtime.open_orders}


def _clean_up(app: _Booted, bot_id: str) -> None:
    """Stops a bot still running (selling its base), then cancels what is
    left. A cancel heard while RUNNING would be laid again."""
    if app.state(bot_id) is not S.STOPPED:
        app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, BaseHandling.SELL_AT_MARKET)
        )
        wait_until(
            "the bot stopped in clean-up", lambda: app.state(bot_id) is S.STOPPED
        )
    for client_order_id in app.tagged_open(bot_id):
        app.client.cancel_order(_SYMBOL, client_order_id)


def _write_report(name: str, content: dict[str, Any]) -> None:
    _REPORTS.mkdir(parents=True, exist_ok=True)
    (_REPORTS / name).write_text(json.dumps(content, indent=2, default=str))


def test_a_grid_rests_its_levels_replaces_an_outside_cancel_and_stops_clean(
    booted: _Booted,
) -> None:
    app = booted
    terms, price = _terms_and_price(app)
    latency_s = _stream_latency_s(app, terms, price)
    config = _grid_config(terms, price)
    created = _command(
        app, CreateBotCommand("testnet grid", "grid", _SPOT, _SYMBOL, config)
    )
    assert created.bot_id is not None
    bot_id = created.bot_id
    report: dict[str, Any] = {"stream_cancel_latency_s": latency_s, "grid": config}
    try:
        started_at = time.monotonic()
        _command(app, StartBotCommand(bot_id))
        _wait_for_state(app, bot_id, S.RUNNING)
        report["start_to_running_s"] = time.monotonic() - started_at
        wait_until(
            "every level resting with the bot's tag",
            lambda: (
                bool(_ladder(app.runtime(bot_id)))
                and app.tagged_open(bot_id) == _ladder(app.runtime(bot_id))
            ),
        )

        cancelled, level_price = next(iter(_ladder(app.runtime(bot_id)).items()))
        app.client.cancel_order(_SYMBOL, cancelled)
        wait_until(
            "the cancelled level laid again under a new id",
            lambda: (
                cancelled not in _ladder(app.runtime(bot_id))
                and level_price in _ladder(app.runtime(bot_id)).values()
                and app.tagged_open(bot_id) == _ladder(app.runtime(bot_id))
            ),
        )

        _command(app, StopBotCommand(bot_id, BaseHandling.SELL_AT_MARKET))
        _wait_for_state(app, bot_id, S.STOPPED)
        wait_until("no tagged order open", lambda: app.tagged_open(bot_id) == {})
    finally:
        try:
            _clean_up(app, bot_id)
        except Exception:
            # Never hides the test's own failure; the log says what is left.
            logger.exception("Testnet grid clean-up failed for bot %s", bot_id)
        _write_report("spot_grid_round_trip.json", report)


def _owner_orders_in(window_s: int, caps: OwnerBudgetCaps) -> int:
    """The most orders one owner at the caps can send in `window_s`: its
    spacing bounds a burst, its per-minute rate bounds anything longer."""
    spacing_s = caps.min_order_spacing.total_seconds()
    by_spacing = math.floor(window_s / spacing_s) + 1 if spacing_s > 0 else math.inf
    by_rate = (
        math.ceil(caps.max_orders_per_minute * window_s / 60)
        if window_s >= 60
        else caps.max_orders_per_minute
    )
    return int(min(by_spacing, by_rate))


def _max_num_orders(info: dict[str, Any]) -> int:
    symbol = next(row for row in info["symbols"] if row["symbol"] == _SYMBOL)
    found = next(
        row for row in symbol["filters"] if row["filterType"] == "MAX_NUM_ORDERS"
    )
    return int(found.get("maxNumOrders", found.get("limit")))


def test_how_many_owner_budgets_one_account_holds(
    spot_testnet_credentials: ExchangeCredentials, tmp_path: Path
) -> None:
    """`EPIC-029A` handed this over. The caps bound each bot's budget, while
    `ORDERS` and `MAX_NUM_ORDERS` bound the whole account, so the number that
    matters is how many owners at the caps fit; the report records it."""
    engine = create_app(_config(tmp_path))
    try:
        caps = engine.context.container.resolve(OwnerBudgetCaps)
    finally:
        engine.stop()
    info = SpotSessionFactory().create_metadata_client().get_exchange_info()
    orders = [row for row in info["rateLimits"] if row["rateLimitType"] == "ORDERS"]
    max_num_orders = _max_num_orders(info)
    windows = []
    for limit in orders:
        window_s = _WINDOW_S[limit["interval"]] * int(limit["intervalNum"])
        per_owner = _owner_orders_in(window_s, caps)
        windows.append(
            {
                **limit,
                "window_s": window_s,
                "one_owner_at_the_caps": per_owner,
                "owners_that_fit": int(limit["limit"]) // per_owner,
            }
        )
    owners_by_open_orders = max_num_orders // caps.max_open_orders
    owners_that_fit = min(
        [owners_by_open_orders, *(window["owners_that_fit"] for window in windows)]
    )
    _write_report(
        "spot_rate_limits.json",
        {
            "venue": _SPOT.value,
            "symbol": _SYMBOL,
            "orders_rate_limits": windows,
            "max_num_orders": max_num_orders,
            "owners_by_open_orders": owners_by_open_orders,
            "owners_that_fit": owners_that_fit,
            "caps": {
                "max_open_orders": caps.max_open_orders,
                "max_orders_per_minute": caps.max_orders_per_minute,
                "min_order_spacing_ms": caps.min_order_spacing.total_seconds() * 1000,
            },
        },
    )

    assert orders, "the venue publishes no ORDERS rate limit"
    assert owners_that_fit >= 1, "one owner at the caps does not fit the account"
