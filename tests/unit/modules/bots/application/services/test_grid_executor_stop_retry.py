"""`EPIC-035C` (H5) — a stop that waited retries itself, boundedly, and says why.

STOPPING had no `stop` edge, so the screen could not offer Stop again, and the
only retry was a trading session closed → open event. A stop that waited on a
refused cancel or an order the exchange had not yet removed stayed STOPPING
until someone changed the session. Now the executor retries on a bounded
schedule (`STOP_RETRY_DELAYS`) and the user can ask again; after the last
retry the bot stays STOPPING with a reason that names the next action. A bot
is still never STOPPED while a tagged order is open.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stop_retry import (
    STOP_RETRY_DELAYS,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    GridWorld,
    grid_world,
)

S = BotLifecycleState
_REFUSED = TradingLimitViolation.OWNER_BUDGET_RATE


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    world.book.requests.clear()
    return world


def _stuck_open(world: GridWorld) -> None:
    """The exchange reports every cancel done and keeps the orders open."""
    world.book.sticky = set(world.book.open)


def test_a_stop_that_waited_on_a_refused_cancel_retries_without_a_session_event() -> (
    None
):
    world = _running()
    world.book.cancel_refusals = [_REFUSED, _REFUSED]

    world.executor.stop(BaseHandling.KEEP)

    assert world.state() is S.STOPPING
    detail = world.runtime().reason_detail
    assert "refused" in detail
    assert "4 order(s) still open" in detail
    assert f"retry 1 of {len(STOP_RETRY_DELAYS)} in 10s" in detail
    assert [retry.delay for retry in world.retries.pending] == [STOP_RETRY_DELAYS[0]]

    world.retries.run_next()

    assert world.state() is S.STOPPING
    assert (
        f"retry 2 of {len(STOP_RETRY_DELAYS)} in 30s" in world.runtime().reason_detail
    )
    assert len(world.retries.pending) == 1

    world.retries.run_next()

    assert world.state() is S.STOPPED
    assert world.book.open == {}
    assert world.retries.pending == []
    assert "waiting" not in world.runtime().reason_detail


def test_stopped_still_requires_zero_open_tagged_orders() -> None:
    world = _running()
    _stuck_open(world)

    world.executor.stop(BaseHandling.KEEP)
    while world.retries.pending:
        assert world.state() is S.STOPPING
        world.retries.run_next()

    assert world.state() is S.STOPPING
    assert world.book.open, "the orders the exchange kept are still open"


def test_exhausted_retries_leave_the_bot_stopping_with_a_named_reason(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = _running()
    _stuck_open(world)

    with caplog.at_level(logging.ERROR, logger="App.Bots.GridExecutor"):
        world.executor.stop(BaseHandling.KEEP)
        runs = 0
        while world.retries.pending:
            world.retries.run_next()
            runs += 1

    assert runs == len(STOP_RETRY_DELAYS)
    assert world.state() is S.STOPPING
    runtime = world.runtime()
    assert runtime.reason is GridReason.USER_STOP
    assert "still open" in runtime.reason_detail
    assert "retries are used up" in runtime.reason_detail
    assert "Stop" in runtime.reason_detail
    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert BOT in errors[0].getMessage()


def test_a_stop_asked_again_in_stopping_starts_a_fresh_round_of_retries() -> None:
    world = _running()
    _stuck_open(world)
    world.executor.stop(BaseHandling.KEEP)
    while world.retries.pending:
        world.retries.run_next()
    world.book.sticky = set()

    world.executor.stop(BaseHandling.KEEP)

    assert world.state() is S.STOPPED
    assert world.book.open == {}


def test_a_stale_retry_does_nothing_once_the_user_asked_again() -> None:
    world = _running()
    _stuck_open(world)
    world.executor.stop(BaseHandling.KEEP)
    world.executor.stop(BaseHandling.KEEP)
    cancels = len(world.book.cancels)
    assert len(world.retries.pending) == 2

    world.retries.run_next()

    assert len(world.book.cancels) == cancels, "the first round's retry is stale"


def test_a_stop_asked_again_keeps_the_reason_and_the_forced_sell() -> None:
    """A stop loss forces selling the base; pressing Stop again with "keep"
    (the dialog's default) must not turn the exit into a keep."""
    world = _running()
    world.session.register_owner_budget_answers(
        OwnerBudgetRegistrationResult(
            None, OwnerInventory(Decimal("4.126"), Decimal(0))
        )
    )
    world.book.cancel_refusals = [_REFUSED]

    world.executor.facts.on_tick(PriceTick.at(Decimal(89)))
    assert world.state() is S.STOPPING
    assert world.runtime().reason is GridReason.STOP_LOSS

    world.executor.stop(BaseHandling.KEEP)

    assert world.runtime().reason is GridReason.STOP_LOSS
    assert world.state() is S.STOPPED
    sells = [r for r in world.book.requests if r.order_type is OrderType.MARKET]
    assert sum(r.quantity for r in sells) == Decimal("4.126")


def test_a_stop_asked_again_can_add_a_sell_the_first_did_not_ask_for() -> None:
    world = _running()
    world.book.cancel_refusals = [_REFUSED]
    world.executor.stop(BaseHandling.KEEP)
    assert not world.runtime().sell_base_on_stop

    world.executor.stop(BaseHandling.SELL_AT_MARKET)

    assert world.runtime().sell_base_on_stop


def test_no_retry_is_scheduled_while_trading_is_off() -> None:
    """A switch-off wait ends with the switch-on event, not with a timer."""
    world = _running()
    world.executor.facts.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)
    world.session.set_enabled(enabled=False)

    world.executor.stop(BaseHandling.KEEP)

    assert world.state() is S.STOPPING
    assert world.retries.pending == []
