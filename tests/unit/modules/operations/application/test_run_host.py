"""`RunHost`: the state machine, the two signals, the wait and the stop policy (`EPIC-038D`).

The host only sequences, so every collaborator is a double derived from its port
(`run_host_doubles.py`) and the host is driven by hand: fire a "signal", read what
it logged and what it asked its collaborators to do. How a stop ends (the second
signal, the deadline, the steps a stop skips) is `test_run_host_stop.py`; the real
signal, in a real process, is `tests/integration/presentation/test_run_process.py`.
"""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_state_machine import (
    HostStateMachine,
    InvalidHostMoveError,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.run_host_doubles import (
    RecordingStep,
    ScriptedPolicy,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.run_host_rig import (
    BRIEF_S,
    Rig,
    transitions,
)


def test_a_started_host_is_serving_and_says_so_to_everyone(
    caplog: pytest.LogCaptureFixture,
) -> None:
    rig = Rig()
    caplog.set_level(logging.INFO, logger="App.Operations.Host")

    rig.host.begin()

    assert rig.host.state is HostState.SERVING
    assert rig.signals.installed
    assert rig.host_signal.calls == ["ready"]
    assert rig.health.states[-1] is HostState.SERVING
    assert rig.health.published[-1] is HostState.SERVING
    assert transitions(caplog) == ["[host] BOOTING -> SERVING"]


def test_a_signal_heard_while_the_app_boots_is_honoured_once_the_host_serves() -> None:
    """The entry point listens before `app.boot()`; a SIGTERM during the restore of the
    bots must not kill the process with workers half-started."""
    rig = Rig()
    rig.host.listen()

    rig.signals.fire()  # the operator stops the service while it boots
    rig.host.begin()

    assert rig.host.state is HostState.SERVING
    assert rig.host.wait_for_stop(timeout_s=BRIEF_S) is True
    rig.host.drain()
    assert rig.host.state is HostState.DRAINING


def test_listening_twice_installs_once_and_ending_unheard_restores_nothing() -> None:
    rig = Rig()

    rig.host.release()  # never listened: nothing of the process's to give back
    rig.host.listen()
    rig.host.listen()
    rig.host.begin()

    assert rig.signals.installed
    assert rig.signals.install_count == 1
    assert rig.signals.restored == 0


def test_the_steps_run_in_order_before_the_host_serves() -> None:
    log: list[str] = []
    rig = Rig(steps=(RecordingStep("first", log), RecordingStep("second", log)))

    rig.host.begin()

    assert log == ["first", "second"]


def test_a_failing_step_fails_the_host_and_hands_the_process_back() -> None:
    log: list[str] = []
    rig = Rig(
        steps=(
            RecordingStep("first", log),
            RecordingStep("broken", log, fails=True),
            RecordingStep("never", log),
        )
    )

    with pytest.raises(RuntimeError, match="broken failed"):
        rig.host.begin()

    assert rig.host.state is HostState.FAILED
    assert log == ["first", "broken"]
    assert rig.host_signal.calls == []
    assert rig.signals.restored == 1


def test_the_first_signal_ends_the_wait_and_a_drain_runs_the_policy_then_stops(
    caplog: pytest.LogCaptureFixture,
) -> None:
    rig = Rig()
    caplog.set_level(logging.INFO, logger="App.Operations.Host")
    rig.host.begin()

    rig.signals.fire()
    rig.host.wait_for_stop()
    rig.host.drain()
    rig.host.end()
    rig.host.release()

    assert rig.policy.applied == 1
    assert rig.host.state is HostState.STOPPED
    assert rig.host_signal.calls == ["ready", "stopping"]
    # STOPPED is said in memory only: the module writes the last snapshot itself,
    # after the bots' workers have closed (`OperationsModule.shutdown`).
    assert rig.health.states == [
        HostState.BOOTING,
        HostState.SERVING,
        HostState.DRAINING,
        HostState.STOPPED,
    ]
    assert rig.health.published == [HostState.SERVING, HostState.DRAINING]
    assert rig.signals.restored == 1
    assert transitions(caplog) == [
        "[host] BOOTING -> SERVING",
        "[host] SERVING -> DRAINING",
        "[host] DRAINING -> STOPPED",
    ]


def test_the_wait_does_not_end_until_a_signal_arrives() -> None:
    rig = Rig()
    rig.host.begin()

    assert rig.host.wait_for_stop(timeout_s=BRIEF_S) is False

    rig.signals.fire()
    assert rig.host.wait_for_stop(timeout_s=BRIEF_S) is True


def test_a_policy_that_does_not_finish_in_time_is_given_up_on_and_named(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy = ScriptedPolicy(leaves=("bot-1", "bot-2"), blocks=True)
    rig = Rig(policy=policy, stop_timeout_s=BRIEF_S)
    caplog.set_level(logging.INFO, logger="App.Operations.Host")
    rig.host.begin()
    rig.signals.fire()

    rig.host.drain()
    rig.host.end()

    assert rig.host.state is HostState.STOPPED
    assert policy.gave_up.wait(5)
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    named = [m for m in warnings if "bot-1" in m and "bot-2" in m]
    assert named, warnings
    assert "STOPPING" in named[0]
    assert "stop timeout" in named[0]


def test_a_policy_that_raises_is_logged_and_the_stop_goes_on(
    caplog: pytest.LogCaptureFixture,
) -> None:
    rig = Rig(policy=ScriptedPolicy(fails=True))
    caplog.set_level(logging.INFO, logger="App.Operations.Host")
    rig.host.begin()
    rig.signals.fire()

    rig.host.drain()
    rig.host.end()

    assert rig.host.state is HostState.STOPPED
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert errors, "the failure was swallowed without a trace"
    assert "the exchange said no" in errors[0].getMessage() + str(errors[0].exc_info)


def test_a_host_that_failed_stays_failed_and_ends_without_a_stop() -> None:
    rig = Rig()
    rig.host.begin()

    rig.host.fail("the snapshot sink is gone")
    rig.host.end()
    rig.host.release()

    assert rig.host.state is HostState.FAILED
    assert rig.policy.applied == 0
    assert rig.signals.restored == 1


def test_ending_twice_changes_nothing_and_the_signals_stay_with_the_host_until_released() -> (
    None
):
    """`app.stop()` closes the workers after the host has ended; a second Ctrl-C then must
    be absorbed, not left to the default action that would kill the process half-way."""
    rig = Rig()
    rig.host.begin()
    rig.signals.fire()
    rig.host.drain()

    rig.host.end()
    rig.host.end()

    assert rig.host.state is HostState.STOPPED
    assert rig.signals.installed and rig.signals.restored == 0

    rig.host.release()
    rig.host.release()

    assert rig.signals.restored == 1


@pytest.mark.parametrize(
    ("path", "refused"),
    [
        ((HostState.SERVING,), HostState.STOPPED),
        ((HostState.SERVING, HostState.DRAINING), HostState.SERVING),
        ((HostState.SERVING, HostState.DRAINING, HostState.STOPPED), HostState.FAILED),
        ((HostState.FAILED,), HostState.SERVING),
    ],
    ids=[
        "serving cannot skip the drain",
        "a drain cannot go back",
        "stopped is final",
        "failed is final",
    ],
)
def test_a_move_the_table_does_not_list_is_refused(
    path: tuple[HostState, ...], refused: HostState
) -> None:
    machine = HostStateMachine()
    for state in path:
        machine.move_to(state)

    with pytest.raises(InvalidHostMoveError):
        machine.move_to(refused)

    assert machine.state is path[-1]
