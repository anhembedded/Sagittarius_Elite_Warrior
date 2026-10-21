"""`EPIC-044B` — a restart answers a bot waiting for its range with RECOVERING (ADR 044 D9, D2, D7).

The order session is closed after a restart and the lease and the budget are gone, so the bot goes
through the reconcile every restored bot goes through; nothing is laid by the restart. While it is
RECOVERING into the wait the watches that protect exposure stay off: it is outside its range by
definition and holds nothing, so its range exit, a stop loss it sits beyond and a quiet feed must
not close, stop or halt it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.protection.protection_futures import (
    ProtectiveStopService,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    GateOutcome,
    GateResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CONFIG,
    GridWorld,
    grid_world,
    quote_at,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.position_world import (
    Gate,
    Marks,
    a_position_world,
)

D = Decimal
S = BotLifecycleState
_BELOW, _INSIDE = D(95), D(121)
_WITH_NO_EXITS = {**CONFIG, "stop_loss": "off", "take_profit": "off"}


def _recovering_into_the_wait(
    config: dict[str, str] | None = None, price: Decimal = _BELOW
) -> GridWorld:
    """A bot saved while AWAITING_RANGE and restored: RECOVERING, nothing on the exchange."""
    world = grid_world(
        state=S.RECOVERING,
        recovering_from=S.AWAITING_RANGE,
        runtime=GridRuntime(()),
        config=config or _WITH_NO_EXITS,
        last_price=price,
    )
    world.hold("0")
    return world


def test_a_restart_turns_a_waiting_bot_into_recovering_that_remembers_the_wait() -> (
    None
):
    world = grid_world(state=S.AWAITING_RANGE, config=_WITH_NO_EXITS, last_price=_BELOW)

    restored = world.store.load(BotId(BOT)).bot.restored(
        datetime(2026, 10, 21, tzinfo=UTC)
    )

    assert restored.state is S.RECOVERING
    assert restored.lifecycle.recovering_from is S.AWAITING_RANGE


def test_the_reconcile_returns_the_bot_to_waiting_and_lays_nothing() -> None:
    world = _recovering_into_the_wait()

    world.executor.resume()

    assert world.state() is S.AWAITING_RANGE
    assert world.book.requests == []


def test_a_bot_that_waits_again_after_a_restart_enters_when_the_price_does() -> None:
    world = _recovering_into_the_wait()
    world.executor.resume()
    quote_at(world, _INSIDE)
    world.monotonic.advance(10)

    world.executor.facts.on_tick(PriceTick.at(_INSIDE))

    assert world.state() is S.RUNNING
    assert world.book.requests


def test_an_order_carrying_the_bots_tag_that_it_never_saved_halts_the_reconcile() -> (
    None
):
    """Nothing was laid by the waiting bot, so a tagged order on the exchange is not its own."""
    ran = grid_world(config=_WITH_NO_EXITS, last_price=_INSIDE)
    ran.executor.start()
    world = _recovering_into_the_wait(price=_INSIDE)
    world.book.open = dict(ran.book.open)

    world.executor.resume()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.UNKNOWN_TAGGED_ORDER


def test_nothing_that_needs_a_position_acts_on_a_bot_recovering_into_the_wait() -> None:
    """A stop loss it sits beyond, a quiet feed and a tick far outside do not touch it."""
    world = _recovering_into_the_wait(config=CONFIG, price=D(85))

    world.executor.facts.on_tick(PriceTick.at(D(85)))
    world.monotonic.advance(10_000)
    world.executor.facts.on_price_age_check()

    assert world.state() is S.RECOVERING
    assert world.runtime().reason is not GridReason.STOP_LOSS
    assert world.runtime().reason is not GridReason.PRICE_FEED_STALE
    assert world.book.requests == []


def test_the_range_exit_close_does_not_close_a_futures_bot_recovering_into_the_wait() -> (
    None
):
    config = {
        **_WITH_NO_EXITS,
        "on_range_exit": "close",
        "direction": "LONG",
        "leverage": "1",
    }
    marks = Marks("90")
    world, _gate = a_position_world(
        state=S.RECOVERING,
        recovering_from=S.AWAITING_RANGE,
        marks=marks,
        config=config,
        last_price=_BELOW,
    )

    world.executor.facts.on_price_age_check()

    assert world.state() is S.RECOVERING
    assert world.book.requests == []


class _DriftingGate(Gate):
    """A venue whose leverage is not the bot's: what the read-only check would call drift."""

    def __init__(self) -> None:
        super().__init__(
            GateResult(
                GateOutcome.SETTINGS_MISMATCH, "leverage 5 on the venue, the bot asks 1"
            )
        )


def test_the_reconcile_does_not_judge_the_futures_settings_of_a_bot_that_has_not_entered() -> (
    None
):
    """Entry makes the leverage and the margin type the bot's; judging them before the wait
    would halt every restarted waiting Futures bot with `SETTINGS_DRIFT`."""
    world, _gate = a_position_world(
        gate=_DriftingGate(),
        state=S.RECOVERING,
        recovering_from=S.AWAITING_RANGE,
        config={**_WITH_NO_EXITS, "direction": "LONG", "leverage": "1"},
        last_price=_BELOW,
        marks=Marks("95"),
    )

    world.executor.resume()

    assert world.state() is S.AWAITING_RANGE
    assert world.runtime().reason is not GridReason.SETTINGS_DRIFT


def test_the_same_drift_still_halts_a_recovering_bot_that_was_running() -> None:
    """The control: the skip is for the wait only."""
    ran, _ = a_position_world(
        config={**CONFIG, "direction": "LONG", "leverage": "1"},
        last_price=_INSIDE,
        marks=Marks("121"),
        opens_positions=True,
    )
    ran.executor.start()
    world, _gate = a_position_world(
        gate=_DriftingGate(),
        state=S.RECOVERING,
        recovering_from=S.RUNNING,
        config={**CONFIG, "direction": "LONG", "leverage": "1"},
        last_price=_INSIDE,
        marks=Marks("121"),
        runtime=ran.runtime(),
    )
    world.book.open = dict(ran.book.open)

    world.executor.resume()

    assert world.runtime().reason is GridReason.SETTINGS_DRIFT


def _meets_a_rate_limit(world: GridWorld) -> None:
    def meets_the_limit() -> None:
        raise ExchangeRateLimitedError(
            timedelta(seconds=60), banned=False, raw_message="slow down"
        )

    world.executor._post("a read", meets_the_limit)


def test_a_rate_limit_met_while_recovering_into_the_wait_does_not_halt_the_bot() -> (
    None
):
    """The bot holds nothing, so a pause has nothing to protect it from (ADR 044 D7)."""
    world = _recovering_into_the_wait()

    _meets_a_rate_limit(world)

    assert world.state() is S.RECOVERING


def test_the_same_rate_limit_halts_a_recovering_bot_that_was_running() -> None:
    """The control: the guard is for the wait only."""
    world = grid_world(
        state=S.RECOVERING, recovering_from=S.RUNNING, runtime=GridRuntime(())
    )

    _meets_a_rate_limit(world)

    assert world.state() is not S.RECOVERING


@pytest.mark.parametrize(
    ("recovering_from", "reads"),
    [(S.AWAITING_RANGE, 0), (S.RUNNING, 1)],
    ids=["into-the-wait", "was-running"],
)
def test_the_protective_stop_is_supervised_only_for_a_bot_that_may_hold_a_position(
    recovering_from: S, reads: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    world, _gate = a_position_world(
        state=S.RECOVERING,
        recovering_from=recovering_from,
        config={**CONFIG, "direction": "LONG", "leverage": "1"},
        marks=Marks("95"),
        last_price=_BELOW,
    )
    context = world.executor._context
    seen: list[int] = []
    monkeypatch.setattr(
        context.gateway.account_reads, "watched_position", lambda: seen.append(1)
    )

    ProtectiveStopService(context, Marks("95")).supervise()

    assert len(seen) == reads
