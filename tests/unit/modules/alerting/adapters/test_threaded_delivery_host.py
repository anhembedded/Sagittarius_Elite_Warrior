"""Lanes on real threads: a slow channel delays no other, publishing never waits."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.threaded_delivery_host import (
    MIN_SLEEP_S,
    ThreadedDeliveryHost,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.wake_signal import (
    WakeSignal,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.worker_liveness import (
    STALL_AFTER,
    WorkerLiveness,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    an_alert,
    build_rig,
)

WAIT_S = 10.0
POLL_S = 30.0


@pytest.fixture
def hosted(tmp_path: Path) -> Iterator[tuple[object, ThreadedDeliveryHost, WakeSignal]]:
    signal = WakeSignal()
    rig = build_rig(tmp_path, wakeup=signal)
    host = ThreadedDeliveryHost(
        rig.delivery,
        tuple(rig.channels),
        signal,
        poll_seconds=30.0,
        housekeeping=rig.hub.flush_due,
        housekeeping_seconds=30.0,
        liveness=WorkerLiveness(rig.clock),
        beacon=lambda: None,
        beacon_seconds=30.0,
    )
    yield rig, host, signal
    host.stop()


def test_a_slow_channel_does_not_delay_another(hosted) -> None:  # type: ignore[no-untyped-def]
    rig, host, _signal = hosted
    gate = threading.Event()
    rig.channels["phone"].gate = gate
    host.start()

    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))

    assert rig.channels["phone"].entered.wait(WAIT_S)
    assert rig.channels["backup"].done.wait(WAIT_S)  # while phone still blocks
    assert not rig.channels["phone"].done.is_set()
    gate.set()
    assert rig.channels["phone"].done.wait(WAIT_S)


def test_publishing_returns_while_a_channel_is_stuck(hosted) -> None:  # type: ignore[no-untyped-def]
    rig, host, _signal = hosted
    gate = threading.Event()
    rig.channels["phone"].gate = gate
    rig.channels["backup"].gate = gate
    host.start()

    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.hub.publish(
        an_alert(AlertKind.BOT_ERROR)
    )  # returns although both channels block

    assert rig.channels["phone"].entered.wait(WAIT_S)
    gate.set()
    assert rig.channels["phone"].done.wait(WAIT_S)


def test_stop_ends_every_lane(hosted) -> None:  # type: ignore[no-untyped-def]
    _rig, host, _signal = hosted
    host.start()

    host.stop()

    assert host.running_lanes() == 0


def test_a_wakeup_that_arrives_between_a_pass_and_the_wait_is_not_lost() -> None:
    signal = WakeSignal()
    seen = signal.generation()

    signal.notify()

    assert signal.wait(seen, timeout=0.0) != seen


def test_housekeeping_runs_the_hubs_flush_without_the_scheduler(tmp_path: Path) -> None:
    """A scheduled job would publish two bus events a second into the Developer
    event log; the host's own thread does not."""
    ticked = threading.Event()
    signal = WakeSignal()
    rig = build_rig(tmp_path, wakeup=signal)
    host = ThreadedDeliveryHost(
        rig.delivery,
        (),
        signal,
        poll_seconds=30.0,
        housekeeping=ticked.set,
        housekeeping_seconds=0.01,
        liveness=WorkerLiveness(rig.clock),
        beacon=lambda: None,
        beacon_seconds=30.0,
    )
    host.start()
    try:
        assert ticked.wait(WAIT_S)
    finally:
        host.stop()
    assert host.running_lanes() == 0


def _host_with(rig, signal, beacon, liveness):  # type: ignore[no-untyped-def]
    return ThreadedDeliveryHost(
        rig.delivery,
        tuple(rig.channels),
        signal,
        poll_seconds=30.0,
        housekeeping=rig.hub.flush_due,
        housekeeping_seconds=0.01,
        liveness=liveness,
        beacon=beacon,
        beacon_seconds=30.0,
    )


def _until(condition) -> bool:  # type: ignore[no-untyped-def]
    """A bounded wait on a named condition: no fixed sleep decides the outcome."""
    deadline = time.monotonic() + WAIT_S
    while not condition():
        if time.monotonic() > deadline:
            return False
        threading.Event().wait(0.005)
    return True


def test_the_beacon_runs_at_once_and_apart_from_the_lanes(tmp_path: Path) -> None:
    """`EPIC-036E1`: a beacon stuck inside a slow monitor delays no delivery."""
    signal = WakeSignal()
    rig = build_rig(tmp_path, wakeup=signal)
    entered, release = threading.Event(), threading.Event()

    def stuck_beacon() -> None:
        entered.set()
        release.wait(WAIT_S)

    host = _host_with(rig, signal, stuck_beacon, WorkerLiveness(rig.clock))
    try:
        host.start()
        assert entered.wait(WAIT_S)  # first pass at once, not after beacon_seconds

        rig.hub.publish(an_alert(AlertKind.BOT_HALTED))

        assert rig.channels["phone"].done.wait(WAIT_S)  # while the beacon still blocks
        assert not release.is_set()
    finally:
        release.set()
        host.stop()


def test_a_wedged_lane_makes_the_worker_not_alive_and_a_released_one_alive_again(
    tmp_path: Path,
) -> None:
    """`EPIC-036E1`: the ping must stop when delivery is wedged, though the process,
    its housekeeping and its other lane carry on."""
    signal = WakeSignal()
    rig = build_rig(tmp_path, wakeup=signal)
    liveness = WorkerLiveness(rig.clock)
    gate = threading.Event()
    rig.channels["phone"].gate = gate
    host = _host_with(rig, signal, lambda: None, liveness)
    try:
        host.start()
        rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
        assert rig.channels["phone"].entered.wait(WAIT_S)
        assert _until(liveness.is_alive)

        rig.clock.advance(STALL_AFTER + timedelta(seconds=1))
        signal.notify()  # every lane that can finish a pass stamps the new instant

        # only the wedged lane is left behind
        assert _until(lambda: liveness.stalled() == ("alerting-lane-phone",))
        assert liveness.is_alive() is False

        gate.set()
        assert _until(liveness.is_alive)
    finally:
        gate.set()
        host.stop()


class _RecordingSignal(WakeSignal):
    """A `WakeSignal` that notes how long each lane asked to sleep, then really waits."""

    def __init__(self) -> None:
        super().__init__()
        self.timeouts: list[float] = []
        self.first_wait = threading.Event()

    def wait(self, seen: int, timeout: float) -> int:
        self.timeouts.append(timeout)
        self.first_wait.set()
        return super().wait(seen, timeout)


@pytest.mark.parametrize(
    ("asked", "sleeps", "case"),
    [
        (None, POLL_S, "no wait: the poll interval"),
        (timedelta(milliseconds=10), MIN_SLEEP_S, "a wait inside the floor: the floor"),
        (timedelta(seconds=1.5), 1.5, "a wait inside the poll: the wait"),
        (timedelta(seconds=90), POLL_S, "a wait past the poll: the poll"),
    ],
    ids=["no-wait", "tiny-wait", "short-wait", "long-wait"],
)
def test_a_lane_sleeps_until_its_channel_may_send_again_not_a_whole_poll(
    tmp_path: Path, asked: timedelta | None, sleeps: float, case: str
) -> None:
    """`EPIC-036C2`: without this a paced Discord channel drops to four messages per poll."""
    signal = _RecordingSignal()
    rig = build_rig(tmp_path, ("phone",), wakeup=signal)
    if asked is not None:
        rig.channels["phone"].script.append(DeliveryResult.retry_later(asked, "wait"))
    host = ThreadedDeliveryHost(
        rig.delivery,
        ("phone",),
        signal,
        poll_seconds=POLL_S,
        housekeeping=rig.hub.flush_due,
        housekeeping_seconds=POLL_S,
        liveness=WorkerLiveness(rig.clock),
        beacon=lambda: None,
        beacon_seconds=POLL_S,
    )
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    try:
        host.start()
        assert signal.first_wait.wait(WAIT_S), case
        assert signal.timeouts[0] == pytest.approx(sleeps), case
    finally:
        host.stop()
