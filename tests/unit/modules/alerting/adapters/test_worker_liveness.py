"""`EPIC-036E1` — progress, not existence: a worker that has not finished a pass for
`stall_after` is not alive."""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.worker_liveness import (
    STALL_AFTER,
    WorkerLiveness,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)

SECOND = timedelta(seconds=1)


def test_with_no_worker_registered_nothing_is_alive() -> None:
    assert WorkerLiveness(FakeAlertClock()).is_alive() is False


def test_a_worker_is_alive_up_to_the_stall_limit_and_not_after() -> None:
    clock = FakeAlertClock()
    liveness = WorkerLiveness(clock)
    liveness.register("lane")

    clock.advance(STALL_AFTER)
    assert liveness.is_alive() is True  # at the boundary

    clock.advance(SECOND)
    assert liveness.is_alive() is False  # one second past it


def test_a_finished_pass_makes_the_worker_alive_again() -> None:
    clock = FakeAlertClock()
    liveness = WorkerLiveness(clock)
    liveness.register("lane")
    clock.advance(STALL_AFTER + SECOND)

    liveness.touch("lane")

    assert liveness.is_alive() is True


def test_one_stalled_worker_among_healthy_ones_is_not_alive() -> None:
    clock = FakeAlertClock()
    liveness = WorkerLiveness(clock)
    liveness.register("lane")
    liveness.register("housekeeping")
    clock.advance(STALL_AFTER + SECOND)

    liveness.touch("housekeeping")

    assert liveness.is_alive() is False


def test_the_stalled_workers_are_named() -> None:
    clock = FakeAlertClock()
    liveness = WorkerLiveness(clock)
    liveness.register("lane")
    liveness.register("housekeeping")
    clock.advance(STALL_AFTER + SECOND)
    liveness.touch("housekeeping")

    assert liveness.stalled() == ("lane",)
