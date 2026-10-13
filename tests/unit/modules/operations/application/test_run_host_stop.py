"""How a stop ends: the second signal, the one deadline, the steps a stop skips (`EPIC-038D`).

The lifecycle (states, steps, the first signal, the policy) is `test_run_host.py`.
The process that really leaves is `tests/integration/presentation/test_run_process.py`;
here the call that ends it is a double.
"""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.run_host_doubles import (
    HandFiredSignalSource,
    RecordingStep,
    ScriptedPolicy,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.run_host_rig import (
    BRIEF_S as _BRIEF_S,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.run_host_rig import (
    Rig as _Rig,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.run_host_rig import (
    warnings_of as _warnings,
)


def test_a_second_signal_during_the_policy_leaves_at_once_and_names_what_it_left(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The policy never finishes by itself; the operator presses the key again."""
    fire: list[HandFiredSignalSource] = []
    policy = ScriptedPolicy(
        leaves=("bot-1",), blocks=True, during=lambda: fire[0].fire()
    )
    rig = _Rig(policy=policy)
    fire.append(rig.signals)
    rig.leaver.on_call = policy.unblock.set  # the process ends, and the policy with it
    caplog.set_level(logging.INFO, logger="App.Operations.Host")
    rig.host.begin()
    rig.signals.fire()

    rig.host.drain()  # the policy would wait forever and the timeout is 30 s

    assert rig.leaver.called.wait(5), "a second signal did not end the process"
    assert rig.leaver.codes == [0]
    named = [m for m in _warnings(caplog) if "second signal" in m and "bot-1" in m]
    assert named, _warnings(caplog)
    assert "running the stop policy" in named[0]
    assert rig.host.state is HostState.STOPPED


def test_a_second_signal_while_the_app_closes_leaves_at_once_too(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`app.stop()` closes each bot's worker, up to 10 s apiece; the key pressed twice
    is the operator deciding not to wait for that either."""
    rig = _Rig(policy=ScriptedPolicy(leaves=("bot-1",)))
    caplog.set_level(logging.INFO, logger="App.Operations.Host")
    rig.host.begin()
    rig.signals.fire()
    rig.host.drain()
    rig.host.end()  # the app begins to stop and does not finish
    assert not rig.leaver.called.is_set(), "one signal alone must not end the process"

    rig.signals.fire()

    assert rig.leaver.called.wait(5), "a signal during app.stop() was absorbed"
    named = [m for m in _warnings(caplog) if "second signal" in m]
    assert named and "closing the app" in named[0] and "bot-1" in named[0], named


def test_the_whole_stop_has_one_deadline_and_passing_it_leaves_and_names_why(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The policy is given up at the stop timeout; the rest of the stop (the probes at
    DRAINING, each worker's close) shares the grace after it. Nothing after that hangs."""
    rig = _Rig(
        policy=ScriptedPolicy(leaves=("bot-9",), blocks=True),
        stop_timeout_s=_BRIEF_S,
        stop_grace_s=_BRIEF_S,
    )
    caplog.set_level(logging.INFO, logger="App.Operations.Host")
    rig.host.begin()
    rig.signals.fire()
    rig.host.drain()
    rig.host.end()  # and app.stop() then hangs on a worker

    assert rig.leaver.called.wait(5), "a stuck app.stop() kept the process alive"
    assert rig.leaver.codes == [0]
    named = [m for m in _warnings(caplog) if "stop deadline" in m]
    assert named and "bot-9" in named[0] and "closing the app" in named[0], named


def test_a_stop_that_finishes_in_time_never_leaves_early() -> None:
    rig = _Rig(stop_timeout_s=_BRIEF_S, stop_grace_s=_BRIEF_S)
    rig.host.begin()
    rig.signals.fire()
    rig.host.drain()
    rig.host.end()
    rig.host.release()  # app.stop() returned

    assert not rig.leaver.called.wait(6 * _BRIEF_S)


def test_a_stop_heard_before_serving_skips_the_steps_that_trade(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`systemctl stop` during a slow restore must not then resume bots or start planned
    ones: the host would drain with orders it had only just opened."""
    log: list[str] = []
    rig = _Rig(
        steps=(
            RecordingStep("report", log),
            RecordingStep("resume", log, trades=True),
            RecordingStep("start-planned", log, trades=True),
        )
    )
    caplog.set_level(logging.INFO, logger="App.Operations.Host")
    rig.host.listen()
    rig.signals.fire()

    rig.host.begin()

    assert log == ["report"]
    assert rig.host.state is HostState.SERVING
    assert rig.host.wait_for_stop(timeout_s=_BRIEF_S) is True
    skipped = [m.getMessage() for m in caplog.records if "skipped" in m.getMessage()]
    assert len(skipped) == 2 and "resume" in skipped[0], skipped


def test_a_stop_that_arrives_between_two_steps_skips_the_trading_ones_after_it() -> (
    None
):
    log: list[str] = []
    fire: list[HandFiredSignalSource] = []
    rig = _Rig(
        steps=(
            RecordingStep("slow report", log, during=lambda: fire[0].fire()),
            RecordingStep("resume", log, trades=True),
        )
    )
    fire.append(rig.signals)

    rig.host.begin()

    assert log == ["slow report"]


def test_a_step_that_does_not_trade_runs_whatever_was_heard() -> None:
    log: list[str] = []
    rig = _Rig(steps=(RecordingStep("report", log), RecordingStep("alerts", log)))
    rig.host.listen()
    rig.signals.fire()

    rig.host.begin()

    assert log == ["report", "alerts"]
