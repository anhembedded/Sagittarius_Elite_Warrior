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
known limit). `grid_testnet_app.stream_latency_s` probes it and returns the
stream's latency, which `EPIC-029E` handed to this task; it is recorded.

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
what is left (`grid_testnet_app.clean_up`). A clean-up failure never hides
the test's own.

What it measured goes to `logs/testnet/spot_grid_round_trip.json`. How many
owner budgets fit the account is `test_spot_rate_limits.py`'s.

Opt-in only, behind this tree's two gates (`conftest.py`).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_planner_market import (
    GetPlannerMarketQuery,
    PlannerMarket,
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.exchange_credentials import (
    ExchangeCredentials,
)
from Sagittarius_Elite_Warrior.tests.testnet.grid_testnet_app import (
    SPOT,
    SYMBOL,
    GridTestnetApp,
    S,
    clean_up,
    composed_on_spot_testnet,
    enable_trading,
    round_to_step,
    spot_testnet_config,
    stream_latency_s,
    wait_for_state,
    write_report,
)
from Sagittarius_Elite_Warrior.tests.testnet.round_trips import wait_until

logger = logging.getLogger("App.Tests.Testnet")

#: Four levels (three gaps) 5% either side of the last price.
_HALF_RANGE = Decimal("0.05")
_GRID_COUNT = 3
#: Every grid order at four times the venue's minimum notional.
_NOTIONAL_MARGIN = 4


@pytest.fixture
def booted(
    spot_testnet_credentials: ExchangeCredentials, tmp_path: Path
) -> Iterator[GridTestnetApp]:
    """The app booted with Spot Testnet on and trading enabled. The credential
    fixture is the gate; the app resolves the keys itself."""
    with composed_on_spot_testnet(spot_testnet_config(tmp_path)) as app:
        enable_trading(app)
        yield app


def _terms_and_price(app: GridTestnetApp) -> tuple[ExchangeTerms, Decimal]:
    market = app.engine.dispatch(
        GetPlannerMarketQuery, GetPlannerMarketQuery(SPOT, SYMBOL)
    )
    assert isinstance(market, PlannerMarket)
    assert market.terms is not None and market.market is not None, market.problem
    return market.terms, market.market.last_price


def _grid_config(terms: ExchangeTerms, price: Decimal) -> dict[str, str]:
    lower = round_to_step(price * (1 - _HALF_RANGE), terms.tick_size, ROUND_FLOOR)
    upper = round_to_step(price * (1 + _HALF_RANGE), terms.tick_size, ROUND_CEILING)
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


def _command(app: GridTestnetApp, command: Any) -> BotCommandResult:
    result = app.engine.dispatch(type(command), command)
    assert isinstance(result, BotCommandResult)
    assert result.accepted, result.message
    return result


def _ladder(runtime: GridRuntime) -> dict[str, Decimal | None]:
    return {order.client_order_id: order.price for order in runtime.open_orders}


def test_a_grid_rests_its_levels_replaces_an_outside_cancel_and_stops_clean(
    booted: GridTestnetApp,
) -> None:
    app = booted
    terms, price = _terms_and_price(app)
    latency_s = stream_latency_s(app, terms, price)
    config = _grid_config(terms, price)
    created = _command(
        app, CreateBotCommand("testnet grid", "grid", SPOT, SYMBOL, config)
    )
    assert created.bot_id is not None
    bot_id = created.bot_id
    report: dict[str, Any] = {"stream_cancel_latency_s": latency_s, "grid": config}
    try:
        started_at = time.monotonic()
        _command(app, StartBotCommand(bot_id))
        wait_for_state(app, bot_id, S.RUNNING)
        report["start_to_running_s"] = time.monotonic() - started_at
        wait_until(
            "every level resting with the bot's tag",
            lambda: (
                bool(_ladder(app.runtime(bot_id)))
                and app.tagged_open(bot_id) == _ladder(app.runtime(bot_id))
            ),
        )

        cancelled, level_price = next(iter(_ladder(app.runtime(bot_id)).items()))
        app.client.cancel_order(SYMBOL, cancelled)
        wait_until(
            "the cancelled level laid again under a new id",
            lambda: (
                cancelled not in _ladder(app.runtime(bot_id))
                and level_price in _ladder(app.runtime(bot_id)).values()
                and app.tagged_open(bot_id) == _ladder(app.runtime(bot_id))
            ),
        )

        _command(app, StopBotCommand(bot_id, BaseHandling.SELL_AT_MARKET))
        wait_for_state(app, bot_id, S.STOPPED)
        wait_until("no tagged order open", lambda: app.tagged_open(bot_id) == {})
    finally:
        try:
            clean_up(app, bot_id)
        except Exception:
            # Never hides the test's own failure; the log says what is left.
            logger.exception("Testnet grid clean-up failed for bot %s", bot_id)
        write_report("spot_grid_round_trip.json", report)
