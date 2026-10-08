"""`EPIC-035F` (M4) — a key the exchange rejects mid-run is named, not mistaken for a switch-off.

A revoked key made the next order fail its connection check, which trading
answered `CONNECTION_NOT_READY` and the bot read as a switch-off: HALTED, with a
reason that says "trading is off" and nothing that says the orders on the
exchange can no longer be cancelled from here. Now the rejection is its own
reason, the bot halts without trying a park that cannot work, says plainly that
its orders may still rest, and a bot that holds orders probes its key between
orders so a revocation is found without waiting for the next fill.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_key_probe import (
    KEY_PROBE_EVERY_SECONDS,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.execute_order_result import (
    ExecuteOrderSafetyGate,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    VENUE,
    GridWorld,
    grid_world,
)

S = BotLifecycleState
_KEY_REJECTED = ExecuteOrderSafetyGate.KEY_REJECTED


def _status(failure: ConnectionFailureKind | None) -> ExchangeConnectionStatus:
    return ExchangeConnectionStatus(
        venue=VENUE,
        reachable=failure is None,
        failure=failure,
        server_time_skew_ms=0,
        usdt_balance=Decimal(10000),
        position_mode=None,
        margin_type=None,
        open_position_count=None,
    )


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    world.executor.on_tick(Decimal(121))
    return world


def _beats(world: GridWorld, seconds: float, every: float = 30.0) -> None:
    """The price watch's heartbeat for `seconds`, the feed alive throughout."""
    elapsed = 0.0
    while elapsed < seconds:
        world.monotonic.advance(every)
        elapsed += every
        world.executor.on_tick(Decimal(121))
        world.executor.on_price_age_check()


def _assert_halted_by_the_key_without_a_cancel(world: GridWorld) -> None:
    assert world.state() is S.HALTED
    runtime = world.runtime()
    assert runtime.reason is GridReason.KEY_REJECTED
    assert "may still rest" in runtime.reason_detail
    assert "cannot" in runtime.reason_detail, "it says this app cannot cancel them"
    assert world.book.cancels == [], "a park with a rejected key cannot work"
    assert world.book.open, "the ladder is where it was"


def test_a_rejected_key_halts_with_key_rejected_not_switch_off() -> None:
    world = _running()
    world.book.refuse_next = [_KEY_REJECTED]

    world.fill(Decimal(110), "2.272")

    _assert_halted_by_the_key_without_a_cancel(world)


def test_a_key_rejected_on_the_order_itself_is_the_same_halt() -> None:
    """The exchange can also answer the order, not the connection check."""
    world = _running()
    world.book.raise_next = [
        OrderRejectedByExchangeError(
            OrderRejectionReason.KEY_REJECTED, "-2015 Invalid API-key"
        )
    ]

    world.fill(Decimal(110), "2.272")

    _assert_halted_by_the_key_without_a_cancel(world)


def test_a_key_rejected_while_starting_refuses_the_start_by_name() -> None:
    world = grid_world()
    world.book.refuse_next = [_KEY_REJECTED]

    world.executor.start()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.KEY_REJECTED
    assert world.book.cancels == []


def test_a_stop_the_exchange_refuses_for_the_key_halts_by_name_instead_of_waiting() -> (
    None
):
    world = _running()
    world.book.cancel_refusals = [_KEY_REJECTED]

    world.executor.stop(BaseHandling.KEEP)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.KEY_REJECTED
    assert world.retries.pending == [], "retrying a revoked key would only fail again"


def test_the_key_is_probed_between_orders() -> None:
    world = _running()
    world.snapshot.answer_with(_status(ConnectionFailureKind.KEY_REJECTED))

    _beats(world, KEY_PROBE_EVERY_SECONDS)

    _assert_halted_by_the_key_without_a_cancel(world)


def test_the_key_is_probed_on_a_bounded_interval_and_not_before() -> None:
    world = _running()
    world.snapshot.answer_with(_status(None))
    checks = world.snapshot.connection_checks

    _beats(world, KEY_PROBE_EVERY_SECONDS / 2)
    assert world.snapshot.connection_checks == checks, "too soon to probe again"

    _beats(world, KEY_PROBE_EVERY_SECONDS)
    assert world.snapshot.connection_checks > checks, "probed within the interval"
    assert world.state() is S.RUNNING, "a good key changes nothing"


def test_a_probe_that_cannot_reach_the_exchange_does_not_halt_the_bot() -> None:
    world = _running()
    world.snapshot.answer_with(_status(ConnectionFailureKind.NETWORK))

    _beats(world, KEY_PROBE_EVERY_SECONDS * 2)

    assert world.state() is S.RUNNING, "a network fault is not a revoked key"


def test_a_bot_at_rest_is_not_probed() -> None:
    world = grid_world(state=S.STOPPED)
    world.snapshot.answer_with(_status(ConnectionFailureKind.KEY_REJECTED))
    checks = world.snapshot.connection_checks

    _beats(world, KEY_PROBE_EVERY_SECONDS * 2)

    assert world.snapshot.connection_checks == checks
    assert world.state() is S.STOPPED
