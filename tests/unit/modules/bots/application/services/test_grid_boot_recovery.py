"""`EPIC-035C` (H6) — what a restart leaves, read and cleaned at boot.

Two halves, both about orders resting under a bot the restart left unmanaged:

  · A RUNNING or PAUSED bot loads RECOVERING and used to reconcile only when
    the order session opened, so its ladder filled with no counter orders and
    nobody was told. Now the boot reads the exchange (open orders and order
    history by client order id, reads only) and puts what it found on the bot.
    Nothing is placed or cancelled by the report.
  · A bot restored from STARTING (HALTED: the start was cut short, maybe with
    part of the ladder on the book) owes a cancel of its tagged orders. The
    restart records the debt on the bot; the boot pays it when the exchange
    lets it, and the switch-on pays it otherwise. A cancel that is refused is
    said, never reported as a clean halt.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_boot_recovery import (
    BotBootRecovery,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_restore_service import (
    BotRestoreService,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.recovery_report import (
    RecoveryReport,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    SYMBOL,
    GridWorld,
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.test_grid_reconciler import (
    filled_while_closed,
    restored,
)

S = BotLifecycleState
_REFUSED = TradingLimitViolation.OWNER_BUDGET_RATE
_AT = datetime(2026, 10, 4, 9, tzinfo=UTC)


def _recovering_with_four_kinds_of_order() -> GridWorld:
    """Four saved orders at 100, 110, 130 and 140. After the restart: 110
    filled while the app was closed, 130 is gone with no history, 100 and 140
    rest, and a tagged order at 105 is one the bot never saved."""
    world = restored()
    world.session.set_enabled(enabled=False)
    filled_while_closed(world, Decimal(110), "2.272")
    world.book.open.pop(world.open_ids_by_price()[Decimal(130)])
    foreign = Order(
        generate_client_order_id(BOT),
        SYMBOL,
        OrderSide.BUY,
        OrderType.LIMIT,
        Decimal("0.5"),
        price=Decimal(105),
    )
    world.book.open[foreign.client_order_id] = foreign
    return world


def test_a_restored_running_bot_reports_what_the_exchange_holds_before_the_session_opens() -> (
    None
):
    world = _recovering_with_four_kinds_of_order()

    BotBootRecovery(world.store, BotExecutors(world.factory)).run()

    expected = RecoveryReport(resting=2, filled_while_closed=1, missing=1, foreign=1)
    runtime = world.runtime()
    assert world.state() is S.RECOVERING
    assert runtime.reason is GridReason.RECOVERY_READ
    assert runtime.reason_detail == expected.words()
    assert world.book.requests == []
    assert world.book.cancels == []
    assert world.owner not in world.session.budgets


def test_the_report_says_when_the_exchange_could_not_be_read() -> None:
    world = restored()
    world.session.set_enabled(enabled=False)
    world.activity.history_unavailable = True
    world.book.open.pop(world.open_ids_by_price()[Decimal(130)])

    BotBootRecovery(world.store, BotExecutors(world.factory)).run()

    runtime = world.runtime()
    assert world.state() is S.RECOVERING
    assert runtime.reason is GridReason.RECOVERY_READ
    assert "could not be read" in runtime.reason_detail
    assert "order history did not answer" in runtime.reason_detail


def test_a_read_that_raises_is_reported_and_does_not_fault_the_bot() -> None:
    world = restored()
    world.session.set_enabled(enabled=False)
    world.activity.open_orders_error = ConnectionError("no route to host")

    BotBootRecovery(world.store, BotExecutors(world.factory)).run()

    runtime = world.runtime()
    assert world.state() is S.RECOVERING
    assert "could not be read" in runtime.reason_detail
    assert "ConnectionError" in runtime.reason_detail
    assert "no route to host" not in runtime.reason_detail


def test_enabling_trading_reconciles_and_clears_the_boot_report() -> None:
    world = restored()
    world.session.set_enabled(enabled=False)
    BotBootRecovery(world.store, BotExecutors(world.factory)).run()
    assert world.runtime().reason is GridReason.RECOVERY_READ
    world.session.set_enabled(enabled=True)

    world.executor.on_switch(True, TradingSwitchCause.ENABLED)

    assert world.state() is S.RUNNING
    assert world.runtime().reason is None
    assert world.runtime().reason_detail == ""


def test_a_bot_that_is_not_recovering_gets_no_boot_report() -> None:
    world = grid_world(state=S.STOPPED)

    BotBootRecovery(world.store, BotExecutors(world.factory)).run()

    assert world.activity.open_order_reads == 0
    assert not world.store.load(BotId(BOT)).runtime


# --- a bot restored from STARTING ---


def _restored_from_starting() -> GridWorld:
    """A start that was cut short with the whole ladder on the book, then the
    real restart rule applied to the saved file."""
    before = grid_world()
    before.executor.start()
    world = grid_world(state=S.STARTING, runtime=before.runtime())
    world.book.open = dict(before.book.open)
    BotRestoreService(world.store, world.clock).restore_all()
    return world


def test_the_restart_records_that_a_start_was_cut_short() -> None:
    world = _restored_from_starting()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.START_INTERRUPTED
    assert "orders may still rest" in world.runtime().reason_detail


def test_a_start_cut_short_before_any_order_still_records_the_debt() -> None:
    world = grid_world(state=S.STARTING)

    BotRestoreService(world.store, world.clock).restore_all()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.START_INTERRUPTED
    BotBootRecovery(world.store, BotExecutors(world.factory)).run()
    assert world.runtime().reason is GridReason.START_INTERRUPTED_CLEARED
    assert "no tagged order was resting" in world.runtime().reason_detail


def test_a_bot_restored_from_starting_cancels_its_tagged_orders() -> None:
    world = _restored_from_starting()
    executors = BotExecutors(world.factory)

    BotBootRecovery(world.store, executors).run()

    runtime = world.runtime()
    assert world.state() is S.HALTED
    assert world.book.open == {}
    assert runtime.open_orders == ()
    assert runtime.reason is GridReason.START_INTERRUPTED_CLEARED
    assert "cancelled 4 tagged order(s)" in runtime.reason_detail


def test_the_cancel_waits_for_the_order_session_and_the_switch_on_pays_it() -> None:
    world = _restored_from_starting()
    world.book.cancel_refusals = [ExecuteOrderSafetyGate.TRADING_SWITCH_OFF]
    executors = BotExecutors(world.factory)

    BotBootRecovery(world.store, executors).run()

    assert world.state() is S.HALTED
    assert len(world.book.open) == 4
    assert world.runtime().reason is GridReason.START_INTERRUPTED
    assert "4 tagged order(s) still rest" in world.runtime().reason_detail
    assert "when trading is enabled" in world.runtime().reason_detail

    executors.for_bot(world.store.load(BotId(BOT)).bot).on_switch(
        True, TradingSwitchCause.ENABLED
    )

    assert world.book.open == {}
    assert world.runtime().reason is GridReason.START_INTERRUPTED_CLEARED


def test_a_cancel_the_exchange_refused_is_said_not_hidden() -> None:
    world = _restored_from_starting()
    world.book.cancel_refusals = [_REFUSED]

    BotBootRecovery(world.store, BotExecutors(world.factory)).run()

    runtime = world.runtime()
    assert world.state() is S.HALTED
    assert len(world.book.open) == 4
    assert runtime.reason is GridReason.START_INTERRUPTED
    assert "may still rest" in runtime.reason_detail
    assert "refused" in runtime.reason_detail


def test_starting_restored_then_trading_enabled_leaves_no_tagged_order() -> None:
    """The router's path with no boot step at all: the switch-on alone pays
    the debt, so a missed boot step cannot leave the ladder behind."""
    world = _restored_from_starting()
    executor = world.factory.create(world.store.load(BotId(BOT)).bot)

    executor.on_switch(True, TradingSwitchCause.ENABLED)

    assert world.book.open == {}
    assert world.state() is S.HALTED


def test_one_bot_that_cannot_be_built_does_not_stop_the_others() -> None:
    """A config the planner refuses must not stop the boot (found by the module
    wiring test, which restores a bot whose config has no grid count)."""
    world = restored()
    world.session.set_enabled(enabled=False)
    broken = grid_world(state=S.RECOVERING, recovering_from=S.RUNNING)
    bad = broken.store.load(BotId(BOT))
    world.store.save(
        StoredBot(
            replace(
                bad.bot,
                bot_id=BotId("bad001"),
                definition=replace(bad.bot.definition, config={"lower": "1"}),
            ),
            {},
        )
    )

    BotBootRecovery(world.store, BotExecutors(world.factory)).run()

    assert world.runtime().reason is GridReason.RECOVERY_READ
