"""`EPIC-029H` — one Grid bot on the real Spot Testnet, through the composed app.

The fake exchange proves the ladder's logic (`test_grid_bot_against_fake_server.py`);
only the real venue proves acceptance, the cancel payload (ADR D8), the order
rate and the user-data stream. So this test boots the app as a person runs
it, with Spot Testnet enabled and the keys read by the app itself, turns
trading on through `EnableTradingCommand` (which starts the venue's user-data
websocket), and drives one narrow Grid with the bots use cases:

1. **Start**: every level the bot's runtime holds is RESTING on the exchange,
   with the bot's tag, and nothing else of the bot's is.
2. **A cancel from outside** (the user, on Binance's site): the bot hears it
   on the stream and lays the same level again under a new id.
3. **Stop**, selling the base: no order carrying the bot's tag stays open.

Narrow on purpose: four levels 5% either side of the last price, at a
capital that keeps every order above the venue's minimum notional, so nothing
should fill while it runs. If one does fill, the counter order is the
executor's ordinary reaction and the assertions still hold.

A second test reads the venue's `exchangeInfo.rateLimits` and the symbol's
`MAX_NUM_ORDERS`, checks the owner-budget caps (ADR O1) fit inside them, and
writes what it read to `logs/testnet/spot_rate_limits.json` for the soak
report (the build container cannot reach Binance, `EPIC-029A`).

Opt-in only, behind this tree's two gates (`conftest.py`). Waits are bounded
polls on named conditions, as `round_trips.py` waits; clean-up (cancel every
tagged order) runs in `finally`.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
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
    tag_of,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.enable_trading_result import (
    EnableTradingResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
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
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from sagittarius_engine.kernel.app import App

_SPOT = TradingVenue.SPOT_TESTNET
_SYMBOL = "BTCUSDT"
_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_DIR = _ROOT / "src" / "config"
_REPORT = _ROOT / "logs" / "testnet" / "spot_rate_limits.json"
#: Four levels (three gaps) 5% either side of the last price.
_HALF_RANGE = Decimal("0.05")
_GRID_COUNT = 3
#: The capital per order is kept at four times the venue's minimum notional.
_NOTIONAL_MARGIN = 4
_TIMEOUT_S = 60.0
_POLL_S = 0.5
S = BotLifecycleState


@dataclass
class _Booted:
    engine: App
    store: IBotStore
    client: ITradingClient

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
        enabled = engine.dispatch(
            EnableTradingCommand, EnableTradingCommand(venue=_SPOT)
        )
        assert isinstance(enabled, EnableTradingResult)
        assert enabled.enabled, f"trading did not turn on: {enabled.block_reason}"
        container = engine.context.container
        ports = container.resolve(IVenueTradingPorts).get(_SPOT)
        yield _Booted(
            engine,
            container.resolve(IBotStore),
            ports.client_factory.create(OrderSubmissionMode.LIVE),
        )
    finally:
        engine.stop()


def _wait_for(what: str, condition: Callable[[], bool]) -> None:
    """Polls `condition` until true, or raises naming `what`: a named
    condition, never a blind sleep."""
    deadline = time.monotonic() + _TIMEOUT_S
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(_POLL_S)
    raise TimeoutError(f"{what} within {_TIMEOUT_S:.0f}s")


def _grid_config(market: PlannerMarket) -> dict[str, str]:
    assert market.terms is not None and market.market is not None, market.problem
    tick = market.terms.tick_size
    price = market.market.last_price
    lower = (price * (1 - _HALF_RANGE) / tick).to_integral_value(ROUND_FLOOR) * tick
    upper = (price * (1 + _HALF_RANGE) / tick).to_integral_value(ROUND_CEILING) * tick
    capital = market.terms.min_notional * _NOTIONAL_MARGIN * (_GRID_COUNT + 1)
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


def test_a_grid_rests_its_levels_replaces_an_outside_cancel_and_stops_clean(
    booted: _Booted,
) -> None:
    app = booted
    market = app.engine.dispatch(
        GetPlannerMarketQuery, GetPlannerMarketQuery(_SPOT, _SYMBOL)
    )
    assert isinstance(market, PlannerMarket)
    created = _command(
        app,
        CreateBotCommand("testnet grid", "grid", _SPOT, _SYMBOL, _grid_config(market)),
    )
    assert created.bot_id is not None
    bot_id = created.bot_id
    try:
        _command(app, StartBotCommand(bot_id))
        _wait_for("the bot running", lambda: app.state(bot_id) is S.RUNNING)
        _wait_for(
            "every level resting with the bot's tag",
            lambda: (
                bool(_ladder(app.runtime(bot_id)))
                and app.tagged_open(bot_id) == _ladder(app.runtime(bot_id))
            ),
        )

        cancelled, price = next(iter(_ladder(app.runtime(bot_id)).items()))
        app.client.cancel_order(_SYMBOL, cancelled)
        _wait_for(
            "the cancelled level laid again under a new id",
            lambda: (
                cancelled not in _ladder(app.runtime(bot_id))
                and price in _ladder(app.runtime(bot_id)).values()
                and app.tagged_open(bot_id) == _ladder(app.runtime(bot_id))
            ),
        )

        _command(app, StopBotCommand(bot_id, BaseHandling.SELL_AT_MARKET))
        _wait_for("the bot stopped", lambda: app.state(bot_id) is S.STOPPED)
        _wait_for("no tagged order open", lambda: app.tagged_open(bot_id) == {})
    finally:
        for client_order_id in app.tagged_open(bot_id):
            app.client.cancel_order(_SYMBOL, client_order_id)


def _symbol_max_orders(info: dict[str, Any]) -> int:
    symbol = next(row for row in info["symbols"] if row["symbol"] == _SYMBOL)
    found = next(
        row for row in symbol["filters"] if row["filterType"] == "MAX_NUM_ORDERS"
    )
    return int(found.get("maxNumOrders", found.get("limit")))


def test_the_owner_budget_caps_fit_the_venue_rate_limits(
    booted: _Booted,
) -> None:
    """`EPIC-029A` handed this over: the caps bound each bot's budget, so they
    must fit what the venue allows one account."""
    info = SpotSessionFactory().create_metadata_client().get_exchange_info()
    orders = [row for row in info["rateLimits"] if row["rateLimitType"] == "ORDERS"]
    max_num_orders = _symbol_max_orders(info)
    caps = booted.engine.context.container.resolve(OwnerBudgetCaps)
    _REPORT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT.write_text(
        json.dumps(
            {
                "venue": _SPOT.value,
                "symbol": _SYMBOL,
                "orders_rate_limits": orders,
                "max_num_orders": max_num_orders,
                "caps": {
                    "max_open_orders": caps.max_open_orders,
                    "max_orders_per_minute": caps.max_orders_per_minute,
                    "min_order_spacing_ms": caps.min_order_spacing.total_seconds()
                    * 1000,
                },
            },
            indent=2,
        )
    )

    assert orders, "the venue publishes no ORDERS rate limit"
    assert caps.max_open_orders <= max_num_orders
    for limit in orders:
        window_s = {"SECOND": 1, "MINUTE": 60, "HOUR": 3600, "DAY": 86400}[
            limit["interval"]
        ] * int(limit["intervalNum"])
        per_minute = int(limit["limit"]) * 60 / window_s
        assert caps.max_orders_per_minute <= per_minute, limit
