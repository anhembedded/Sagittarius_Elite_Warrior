"""`EPIC-047F` - the bridge's `bot_log` call: read-only, bounded by the host's limits, one bot's file, no stream held."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_bot_log import (
    BridgeLogLine,
    BridgeLogPage,
    IBridgeBotLog,
)
from Sagittarius_Elite_Warrior.tests.unit.support.wire.bridge.bridge_world import Desk


class FakeBotLog(IBridgeBotLog):
    def __init__(self) -> None:
        self.asked: list[tuple[str, int]] = []

    def read(self, bot_id: str, since: int) -> BridgeLogPage:
        self.asked.append((bot_id, since))
        line = BridgeLogLine(since + 5, "2026-11-25T10:00:00+00:00", "INFO", "fill")
        return BridgeLogPage((line,), line.seq)


def _desk(log: IBridgeBotLog | None) -> Desk:
    desk = Desk(bot_log=log)
    desk.greet()
    return desk


def test_a_call_returns_the_lines_and_the_cursor_and_asks_the_port_once() -> None:
    log = FakeBotLog()
    desk = _desk(log)

    result = desk.result_of(desk.call("bot_log", bot_id="ab12cd", since=10))

    assert result == {
        "lines": [
            {
                "seq": 15,
                "at": "2026-11-25T10:00:00+00:00",
                "level": "INFO",
                "text": "fill",
            }
        ],
        "next": 15,
    }
    assert log.asked == [("ab12cd", 10)]


def test_since_defaults_to_the_newest_lines() -> None:
    log = FakeBotLog()
    desk = _desk(log)

    desk.result_of(desk.call("bot_log", bot_id="ab12cd"))

    assert log.asked == [("ab12cd", 0)]


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"bot_id": 5},
        {"bot_id": "../etc/x"},
        {"bot_id": "AB12CD"},
        {"bot_id": "ab12cd", "since": -1},
        {"bot_id": "ab12cd", "since": "1"},
        {"bot_id": "ab12cd", "since": True},
    ],
    ids=str,
)
def test_a_malformed_call_is_a_call_error_and_reads_nothing(
    params: dict[str, object],
) -> None:
    log = FakeBotLog()
    desk = _desk(log)

    call_id = desk.call("bot_log", **params)

    assert desk.error_of(call_id)["code"] == "bad_bot_log"
    assert log.asked == []


def test_a_build_with_no_log_says_so_and_the_link_stays_up() -> None:
    desk = _desk(None)

    call_id = desk.call("bot_log", bot_id="ab12cd")

    assert desk.error_of(call_id)["code"] == "no_bot_log"
    assert desk.session.exit_code is None


def test_the_call_holds_no_stream_nothing_arrives_after_the_answer() -> None:
    desk = _desk(FakeBotLog())
    desk.result_of(desk.call("bot_log", bot_id="ab12cd"))
    sent = len(desk.out)

    desk.advance(1.0)

    assert [m for m in desk.out[sent:] if m["type"] not in ("ping", "pong")] == []
