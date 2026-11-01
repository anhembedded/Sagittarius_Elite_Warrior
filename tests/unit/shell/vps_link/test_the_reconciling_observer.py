"""`EPIC-047E` (AC6) - each welcomed link settles the commands the last one lost, a few times, and only when there are some.

The business promise: the supervisor's observer still hands every call to the world, and after a link comes up with an
unsettled command in the ledger the host is asked again a bounded number of times while it has recorded nothing; with
nothing to settle no thread is started.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

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


def _observer(
    ledger: UnansweredLedger, remaining: list[int]
) -> tuple[
    ReconcilingObserver, _Inner, _Reconciler, list[Callable[[], None]], list[float]
]:
    inner, reconciler = _Inner(), _Reconciler(remaining)
    spawned: list[Callable[[], None]] = []
    slept: list[float] = []
    observer = ReconcilingObserver(
        inner, ledger, reconciler, spawned.append, slept.append
    )
    return observer, inner, reconciler, spawned, slept


def _ledger_with_one() -> UnansweredLedger:
    ledger = UnansweredLedger()
    ledger.add("a" * 32, HostControlRequest(HostControlAction.START, "b-0001"))
    return ledger


def test_every_call_still_reaches_the_world() -> None:
    observer, inner, *_ = _observer(UnansweredLedger(), [])

    observer.on_status(LinkStatus(LinkState.CONNECTED, "connected"))
    observer.on_event(None, {})  # type: ignore[arg-type]
    observer.on_link_up(None, None)  # type: ignore[arg-type]

    assert inner.calls == ["status", "event", "up"]


def test_a_link_up_with_nothing_unsettled_starts_no_thread() -> None:
    observer, _, _, spawned, _ = _observer(UnansweredLedger(), [])

    observer.on_link_up(None, None)  # type: ignore[arg-type]

    assert spawned == []


def test_a_link_up_with_a_lost_command_asks_the_host_after_the_world_took_its_snapshot() -> (
    None
):
    observer, inner, reconciler, spawned, _ = _observer(_ledger_with_one(), [0])

    observer.on_link_up(None, None)  # type: ignore[arg-type]
    assert inner.calls == ["up"] and reconciler.passes == 0
    spawned[0]()

    assert reconciler.passes == 1


def test_while_the_host_has_recorded_nothing_it_is_asked_again_a_bounded_number_of_times() -> (
    None
):
    observer, _, reconciler, spawned, slept = _observer(
        _ledger_with_one(), [1] * PASSES
    )

    observer.on_link_up(None, None)  # type: ignore[arg-type]
    spawned[0]()

    assert reconciler.passes == PASSES
    assert slept == [PAUSE_S] * (PASSES - 1)


def test_it_stops_asking_once_everything_is_settled() -> None:
    observer, _, reconciler, spawned, slept = _observer(_ledger_with_one(), [1, 0])

    observer.on_link_up(None, None)  # type: ignore[arg-type]
    spawned[0]()

    assert reconciler.passes == 2
    assert slept == [PAUSE_S]
