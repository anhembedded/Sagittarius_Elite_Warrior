"""`EPIC-039E` — a running bot notices that the venue's settings are no longer the ones it asked for.

@details Business promise: someone changing leverage or margin type in the Binance app is a
**halt that names both values**, never a silent re-set and never a ladder that goes on with
the wrong leverage. The check runs where the bot already reconciles with the exchange (a
restart, a stream gap, a sleep); a setting that cannot be read waits and does not halt.
The venue is Spot in this world; the gate behind the executor is the port's own, so the
check is the same one a Futures bot gets (`039H` binds the Futures gate).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_venue_settings_gate import (
    IVenueSettingsGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    ENSURED,
    GateOutcome,
    GateRequest,
    GateResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.gap_world import (
    running,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
)

S = BotLifecycleState


class _Gate(IVenueSettingsGate):
    """A venue whose answer a test sets, recording what it was asked."""

    def __init__(self) -> None:
        self.answer = ENSURED
        self.asked: list[GateRequest] = []
        self.ensured = 0

    def ensure(self, request: GateRequest) -> GateResult:
        self.ensured += 1
        return ENSURED

    def verify(self, request: GateRequest) -> GateResult:
        self.asked.append(request)
        return self.answer


def test_changed_leverage_between_polls_halts_with_settings_drift() -> None:
    gate = _Gate()
    world = running(gate)
    world.executor.facts.reconcile_after_gap()
    assert world.state() is S.RUNNING

    gate.answer = GateResult(
        GateOutcome.SETTINGS_MISMATCH, "BTCUSDT: leverage 3 asked, exchange says 7"
    )
    world.executor.facts.reconcile_after_gap()  # a disagreement is confirmed once
    world.executor.facts.reconcile_after_gap()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.SETTINGS_DRIFT
    assert "leverage 3 asked, exchange says 7" in world.runtime().reason_detail


def test_the_bot_never_sets_the_venue_again_by_itself() -> None:
    gate = _Gate()
    world = running(gate)
    gate.answer = GateResult(
        GateOutcome.SETTINGS_MISMATCH, "x: leverage 3 asked, exchange says 7"
    )

    world.executor.facts.reconcile_after_gap()
    world.executor.facts.reconcile_after_gap()

    assert gate.ensured == 0


def test_the_check_asks_for_the_leverage_and_margin_the_bot_named() -> None:
    gate = _Gate()
    world = running(gate)

    world.executor.facts.reconcile_after_gap()

    (request,) = gate.asked
    assert (request.symbol, request.leverage) == (
        SYMBOL,
        1,
    )  # a legacy definition: leverage 1
    assert request.margin_mode.value == "isolated"


def test_settings_that_cannot_be_read_wait_and_do_not_halt() -> None:
    gate = _Gate()
    world = running(gate)
    gate.answer = GateResult(GateOutcome.SETTINGS_UNREADABLE, "timed out")

    world.executor.facts.reconcile_after_gap()
    world.executor.facts.reconcile_after_gap()

    assert world.state() is S.RUNNING


def test_a_spot_bot_with_the_default_gate_is_never_halted_by_it() -> None:
    world = running()

    world.executor.facts.reconcile_after_gap()
    world.executor.facts.reconcile_after_gap()

    assert world.state() is S.RUNNING
