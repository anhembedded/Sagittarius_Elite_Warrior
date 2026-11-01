"""`EPIC-047E` (AC6) - each welcomed link settles the commands the last one lost, a few times, and only when there are some.

The business promise: the supervisor's observer still hands every call to the world, and after a link comes up with an
unsettled command in the ledger the host is asked again a bounded number of times while it has recorded nothing; with
nothing to settle no thread is started.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlAction,
    HostControlRequest,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.command_reconciler import (
    CommandReconciler,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.reconciling_observer import (
    PASSES,
    PAUSE_S,
    STILL_UNSETTLED_WORDS,
    ReconcilingObserver,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.unanswered_ledger import (
    UnansweredLedger,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_status import (
    LinkState,
    LinkStatus,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.link_supervisor import (
    ConnectionEpoch,
    ILinkObserver,
)


class _Inner(ILinkObserver):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def on_status(self, status: LinkStatus) -> None:
        self.calls.append("status")

    def on_link_up(self, link: Any, epoch: ConnectionEpoch) -> None:
        self.calls.append("up")

    def on_event(self, epoch: ConnectionEpoch, event: dict[str, object]) -> None:
        self.calls.append("event")


class _Reconciler(CommandReconciler):
    """The real class with the host's answer scripted: how many are unsettled after each pass."""

    def __init__(self, remaining: list[int]) -> None:
        self._remaining = remaining
        self.passes = 0

    def reconcile(self) -> int:
        self.passes += 1
        return self._remaining.pop(0)


class _Rig:
    def __init__(self, ledger: UnansweredLedger, remaining: list[int]) -> None:
        self.inner = _Inner()
        self.reconciler = _Reconciler(remaining)
        self.spawned: list[Callable[[], None]] = []
        self.slept: list[float] = []
        self.told: list[str] = []
        self.observer = ReconcilingObserver(
            self.inner,
            ledger,
            self.reconciler,
            self.told.append,
            self.spawned.append,
            self.slept.append,
        )


def _ledger_with_one() -> UnansweredLedger:
    ledger = UnansweredLedger()
    ledger.add("a" * 32, HostControlRequest(HostControlAction.START, "b-0001"))
    return ledger


def test_every_call_still_reaches_the_world() -> None:
    rig = _Rig(UnansweredLedger(), [])

    rig.observer.on_status(LinkStatus(LinkState.CONNECTED, "connected"))
    rig.observer.on_event(None, {})  # type: ignore[arg-type]
    rig.observer.on_link_up(None, None)  # type: ignore[arg-type]

    assert rig.inner.calls == ["status", "event", "up"]


def test_a_link_up_with_nothing_unsettled_starts_no_thread() -> None:
    rig = _Rig(UnansweredLedger(), [])

    rig.observer.on_link_up(None, None)  # type: ignore[arg-type]

    assert rig.spawned == []


def test_a_link_up_with_a_lost_command_asks_the_host_after_the_world_took_its_snapshot() -> (
    None
):
    rig = _Rig(_ledger_with_one(), [0])

    rig.observer.on_link_up(None, None)  # type: ignore[arg-type]
    assert rig.inner.calls == ["up"] and rig.reconciler.passes == 0
    rig.spawned[0]()

    assert rig.reconciler.passes == 1
    assert rig.told == []


def test_while_the_host_has_recorded_nothing_it_is_asked_a_bounded_number_of_times_then_the_person_is_told_once() -> (
    None
):
    rig = _Rig(_ledger_with_one(), [1] * PASSES)

    rig.observer.on_link_up(None, None)  # type: ignore[arg-type]
    rig.spawned[0]()

    assert rig.reconciler.passes == PASSES
    assert rig.slept == [PAUSE_S] * (PASSES - 1)
    assert rig.told == [STILL_UNSETTLED_WORDS]


def test_it_stops_asking_once_everything_is_settled() -> None:
    rig = _Rig(_ledger_with_one(), [1, 0])

    rig.observer.on_link_up(None, None)  # type: ignore[arg-type]
    rig.spawned[0]()

    assert rig.reconciler.passes == 2
    assert rig.slept == [PAUSE_S]
    assert rig.told == []


def test_a_second_run_while_the_first_still_sleeps_does_nothing() -> None:
    """A flapping link starts a second thread; two of them would tell the person about one command twice."""
    rig = _Rig(_ledger_with_one(), [1, 0])
    rig.observer.on_link_up(None, None)  # type: ignore[arg-type]
    rig.observer.on_link_up(None, None)  # type: ignore[arg-type]
    first, second = rig.spawned
    rig.observer._sleep = lambda _s: second()  # type: ignore[method-assign]

    first()

    assert rig.reconciler.passes == 2  # the nested second run asked nothing


def test_a_failure_in_the_thread_is_logged_under_the_tabs_namespace_not_lost(
    caplog: pytest.LogCaptureFixture,
) -> None:
    rig = _Rig(
        _ledger_with_one(), []
    )  # an empty script: the first ask raises IndexError
    rig.observer.on_link_up(None, None)  # type: ignore[arg-type]

    with caplog.at_level(logging.ERROR, logger="App.VpsTab"):
        rig.spawned[0]()

    assert any("[vps-command]" in record.getMessage() for record in caplog.records)
