"""`EPIC-028M` — `DeskSessionControls`: one venue's Emergency Stop, over the
verified `FakeTradingSession`.

@details These carry the single Trading screen's Emergency Stop regressions
onto the class that replaced its copy of that behaviour, when the screen left:
`BUG-089` (a second stop is never sent) and `BUG-093` (a stop's later steps are
reported by no event, so the desk is asked to read its tables again).
`EPIC-034C` removed the Enable/Disable toggle it also carried. Answers are held
(`HeldThreadManager`) so a test can act while one is still out.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.emergency_stop_result import (
    EmergencyStopResult,
    EmergencyStopStepResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_trading_session import (
    FakeTradingSession,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_session_controls import (
    DeskSessionControls,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

from .order_entry_fixtures import HeldThreadManager

_DONE = EmergencyStopStepResult(succeeded=True, detail="done")
_FAILED = EmergencyStopStepResult(succeeded=False, detail="APIError -2011")


@dataclass
class Seen:
    """Everything the controls said, in order."""

    statuses: list[tuple[str, bool]] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    rereads: int = 0

    @property
    def last_status(self) -> tuple[str, bool]:
        return self.statuses[-1]


@dataclass
class Rig:
    controls: DeskSessionControls
    session: FakeTradingSession
    threads: HeldThreadManager
    seen: Seen


@pytest.fixture
def rig(qapp) -> Rig:
    session, threads, seen = FakeTradingSession(), HeldThreadManager(), Seen()
    controls = DeskSessionControls(session, threads, TradingVenue.FUTURES_TESTNET)
    controls.statusChanged.connect(lambda text, err: seen.statuses.append((text, err)))
    controls.logged.connect(seen.logs.append)

    def count_reread() -> None:
        seen.rereads += 1

    controls.accountChanged.connect(count_reread)
    return Rig(controls, session, threads, seen)


def _stop(
    *,
    orders: EmergencyStopStepResult = _DONE,
    confirmed: bool = True,
    still_open: tuple = (),
) -> EmergencyStopResult:
    return EmergencyStopResult(
        trading_disabled=_DONE,
        orders_cancelled=orders,
        positions_closed=_DONE,
        final_open_orders=still_open,
        final_state_confirmed=confirmed,
    )


# -- Emergency Stop ------------------------------------------------------ #


def test_a_full_stop_reports_success_logs_each_step_and_rereads(rig: Rig) -> None:
    rig.session.set_enabled(enabled=True)
    rig.session.emergency_stop_answers(_stop())

    rig.controls.emergency_stop()
    rig.threads.run(0)

    assert rig.session.emergency_stops == 1
    assert rig.seen.last_status == ("Emergency stop completed.", False)
    assert rig.seen.logs[0] == "EMERGENCY STOP"
    assert any("Cancel pending orders" in line for line in rig.seen.logs)
    assert rig.seen.rereads == 1  # `BUG-093`: no event reports steps 2-3


def test_a_partial_stop_reads_as_a_failure(rig: Rig) -> None:
    rig.session.emergency_stop_answers(_stop(orders=_FAILED))

    rig.controls.emergency_stop()
    rig.threads.run(0)

    text, is_error = rig.seen.last_status
    assert is_error is True
    assert "PARTIALLY FAILED" in text
    assert any("APIError -2011" in line for line in rig.seen.logs)


def test_an_unconfirmed_final_state_warns_and_still_rereads(rig: Rig) -> None:
    """`BUG-093` — when even the confirming read failed, the desk says the
    tables may lag instead of presenting them as the truth."""
    rig.session.emergency_stop_answers(_stop(confirmed=False))

    rig.controls.emergency_stop()
    rig.threads.run(0)

    assert any(line.startswith("[WARNING]") for line in rig.seen.logs)
    assert rig.seen.rereads == 1


def test_a_stop_that_raises_is_reported_not_raised(rig: Rig) -> None:
    rig.session.set_enabled(enabled=True)
    rig.session.emergency_stop_raises(RuntimeError("timeout"))

    rig.controls.emergency_stop()
    rig.threads.run(0)  # must not raise

    text, is_error = rig.seen.last_status
    assert is_error is True
    assert "timeout" in text
    assert rig.seen.logs[-1] == "[ERROR] Emergency stop failed: timeout"
    assert rig.session.snapshot().enabled is True  # nothing was closed


def test_a_second_stop_while_one_runs_is_not_sent_twice(rig: Rig) -> None:
    """`BUG-089` — the button is never disabled, so the second press is
    answered in words, never sent as a second stop racing the first."""
    rig.controls.emergency_stop()

    rig.controls.emergency_stop()

    assert len(rig.threads.pending) == 1
    assert rig.seen.last_status == (
        "Emergency stop in progress — the request was already sent.",
        False,
    )
