"""Lanes on real threads: a slow channel delays no other, publishing never waits."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.threaded_delivery_host import (
    ThreadedDeliveryHost,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.wake_signal import (
    WakeSignal,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    an_alert,
    build_rig,
)

WAIT_S = 10.0


@pytest.fixture
def hosted(tmp_path: Path) -> Iterator[tuple[object, ThreadedDeliveryHost, WakeSignal]]:
    signal = WakeSignal()
    rig = build_rig(tmp_path, wakeup=signal)
    host = ThreadedDeliveryHost(
        rig.delivery, tuple(rig.channels), signal, poll_seconds=30.0
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
