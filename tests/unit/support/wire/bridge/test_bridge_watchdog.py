"""`EPIC-047C` - a bridge whose desktop froze ends itself, whatever `sshd` believes."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.wire.bridge.bridge_protocol import (
    EXIT_ENDED,
    EXIT_IDLE,
    HEARTBEAT_S,
    IDLE_WATCHDOG_S,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import Desk


def _greeted() -> Desk:
    desk = Desk()
    desk.greet()
    return desk


def test_a_desktop_that_goes_silent_ends_the_session_with_status_6() -> None:
    desk = _greeted()

    desk.advance(IDLE_WATCHDOG_S - 0.5)
    assert desk.session.exit_code is None
    desk.advance(1.0)

    assert desk.session.exit_code == EXIT_IDLE


def test_a_ping_at_a_third_of_the_watchdog_keeps_the_session_for_as_long_as_it_comes() -> (
    None
):
    desk = _greeted()

    for _ in range(20):
        desk.advance(HEARTBEAT_S)
        desk.feed({"type": "ping"})

    assert desk.session.exit_code is None
    assert len(desk.sent("pong")) == 20


def test_any_line_resets_the_watchdog_not_only_a_ping() -> None:
    desk = _greeted()

    desk.advance(IDLE_WATCHDOG_S - 1)
    desk.call("snapshot")
    desk.advance(IDLE_WATCHDOG_S - 1)

    assert desk.session.exit_code is None


def test_the_bridge_asks_for_pings_three_times_as_often_as_it_tolerates_silence() -> (
    None
):
    assert IDLE_WATCHDOG_S / HEARTBEAT_S == 3


def test_an_input_that_closes_ends_the_session_cleanly() -> None:
    desk = _greeted()

    desk.session.ended()

    assert desk.session.exit_code == EXIT_ENDED


def test_a_session_that_ended_for_one_reason_keeps_that_reason() -> None:
    desk = _greeted()
    desk.advance(IDLE_WATCHDOG_S + 1)

    desk.session.ended()
    desk.feed({"type": "ping"})

    assert desk.session.exit_code == EXIT_IDLE
    assert desk.sent("pong") == []
