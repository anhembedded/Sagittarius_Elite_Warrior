"""`BUG-241` - a Stop that closes in several slices is not refused by the budget's spacing or rate.

@details A Spot exit sells the base in slices at or below trading's per-order cap, one request after
the other (`send_exit_slices`) and with no turn on the pacer: a stop must never wait behind a
neighbour's ladder. Trading judged each slice like a placement, so with the production limits (one
order at least 250 ms after the previous, at most 60 a minute) the second slice, sent a request
after the first, was refused `owner_budget_spacing`, and the bot halted with the rest of its base
unsold. A Futures close is reduce-only and already exempt (`EPIC-039L`); the second journey keeps
that true.

The journeys run the composed app and the production executor against the venue's fake with the
production limits put back (the journeys' default has no spacing), and the clock trading judges by
is a virtual one that does not move while the exit runs: a fake answers in milliseconds, a real
exchange in a few hundred, and the exit must not depend on which (`testing-rule.md`: no sleeps).
"""

from __future__ import annotations

import pytest
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
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .futures_bots_world import GRID as FUTURES_GRID
from .futures_bots_world import BootedFuturesBots, booted_futures_bots
from .futures_fake_exchange import FUTURES, SYMBOL
from .grid_fake_exchange import GRID as SPOT_GRID
from .grid_fake_exchange import SPOT, BootedApp, FakeExchange, booted
from .virtual_order_time import VirtualTime, pacers_on, trading_reads

S = BotLifecycleState

#: The production spacing (ADR O1): 250 ms between two orders of one bot.
PRODUCTION_SPACING = {"trading.bot_limits.min_order_spacing_ms": 250}
#: A rate no exit of two slices fits in: the second slice is the one an order budget would refuse.
ONE_ORDER_A_MINUTE = {
    "trading.bot_limits.min_order_spacing_ms": 0,
    "trading.bot_limits.max_orders_per_minute": 1,
}
LIMITS = {"spacing": PRODUCTION_SPACING, "rate": ONE_ORDER_A_MINUTE}


@pytest.fixture
def virtual_time(monkeypatch: pytest.MonkeyPatch) -> VirtualTime:
    time = VirtualTime()
    trading_reads(monkeypatch, time)
    return time


def _created(
    app: BootedApp | BootedFuturesBots,
    venue: TradingVenue,
    symbol: str,
    config: dict[str, str],
) -> str:
    created = app.engine.dispatch(
        CreateBotCommand,
        CreateBotCommand("sliced exit", "grid", venue, symbol, config),
    )
    assert isinstance(created, BotCommandResult)
    assert created.bot_id is not None, created.message
    return created.bot_id


@pytest.mark.parametrize("limits", LIMITS.values(), ids=LIMITS.keys())
def test_a_spot_stop_that_sells_the_base_in_slices_is_not_refused_by_spacing_or_rate(
    exchange: FakeExchange, virtual_time: VirtualTime, limits: dict[str, object]
) -> None:
    with booted(exchange, pacers=pacers_on(virtual_time), limits=limits) as app:
        bot_id = _created(app, SPOT, "BTCUSDT", SPOT_GRID)
        started = app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))
        assert isinstance(started, BotCommandResult) and started.accepted
        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.RUNNING, (
            runtime.reason,
            runtime.reason_detail,
        )
        held = app.urls.spot_account.free_balance("BTC")

        stopped = app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, ExposureHandling.CLOSE_AT_MARKET)
        )
        app.deliver()

        assert isinstance(stopped, BotCommandResult) and stopped.accepted
        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.STOPPED, (
            app.bot(bot_id).state,
            runtime.reason,
            runtime.reason_detail,
        )
        assert app.urls.spot_account.free_balance("BTC") < held, (
            "the base the bot bought was sold"
        )


@pytest.mark.parametrize("limits", LIMITS.values(), ids=LIMITS.keys())
def test_a_futures_stop_that_closes_the_position_in_slices_is_not_refused_by_spacing_or_rate(
    futures: FakeExchange, virtual_time: VirtualTime, limits: dict[str, object]
) -> None:
    with booted_futures_bots(
        futures, pacers=pacers_on(virtual_time), limits=limits
    ) as app:
        bot_id = _created(app, FUTURES, SYMBOL, FUTURES_GRID)
        started = app.engine.dispatch(StartBotCommand, StartBotCommand(bot_id))
        assert isinstance(started, BotCommandResult) and started.accepted
        assert app.bot(bot_id).state is S.RUNNING
        assert app.position() > 0

        stopped = app.engine.dispatch(
            StopBotCommand, StopBotCommand(bot_id, ExposureHandling.CLOSE_AT_MARKET)
        )
        app.deliver()

        assert isinstance(stopped, BotCommandResult) and stopped.accepted
        runtime = app.runtime(bot_id)
        assert app.bot(bot_id).state is S.STOPPED, (
            app.bot(bot_id).state,
            runtime.reason,
            runtime.reason_detail,
        )
        assert app.position() == 0
