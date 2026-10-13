"""The health line the host writes is made from the snapshot it just published (`EPIC-038D`).

One source for the line and for `status`: the line is not a second measurement. These
tests build a snapshot the way the contributors do and read the line back with the
parser a monitor would use.
"""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    STATUS_KEY,
    UNAVAILABLE,
)
from Sagittarius_Elite_Warrior.src.core.contracts.report import JsonValue
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line import (
    BotCount,
    format_health_line,
    parse_health_line,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_health_line import (
    health_line_of,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.status_world import (
    snapshot_aged,
)

_BOTS: dict[str, JsonValue] = {
    "total": 4,
    "states": {"RUNNING": 3, "PAUSED": 1, "RECOVERING": 0, "STOPPED": 7},
}
_MARKET: dict[str, JsonValue] = {"tick_age_s": 2, "feeds": {"spot:BTCUSDT": 2}}
_TRADING: dict[str, JsonValue] = {
    "user_stream": {},
    "stream_down_s": 5,
    "skew_ms": -120,
}


def _line(sections: dict[str, dict[str, JsonValue]], rss_mb: int | None = 310):
    snapshot = snapshot_aged(0, sections)
    return health_line_of(snapshot, rss_mb)


def test_the_line_reads_each_field_from_its_section() -> None:
    line = _line({"bots": _BOTS, "market_data": _MARKET, "trading": _TRADING})

    assert line.state is HostState.SERVING
    assert line.up_s == 3600  # `snapshot_aged` starts the host an hour before "now"
    assert line.tick_age_s == 2
    assert line.stream_down_s == 5
    assert line.skew_ms == -120
    assert line.rss_mb == 310


def test_the_bots_are_counted_running_paused_halted_recovering_zeros_included() -> None:
    line = _line({"bots": _BOTS})

    assert line.bots == (
        BotCount("running", 3),
        BotCount("paused", 1),
        BotCount("halted", 0),
        BotCount("recovering", 0),
    )


def test_a_stale_feed_is_a_large_tick_age_on_the_line() -> None:
    stale = {"tick_age_s": 900, "feeds": {"spot:BTCUSDT": 900}}

    line = _line({"bots": _BOTS, "market_data": stale, "trading": _TRADING})

    assert parse_health_line(format_health_line(line)).tick_age_s == 900


def test_a_feed_nobody_opened_is_na_not_zero() -> None:
    line = _line({"market_data": {"tick_age_s": None, "feeds": {}}})

    assert line.tick_age_s is None
    assert "tick_age_s=na" in format_health_line(line)


def test_a_stream_nobody_reported_is_na_and_a_connected_one_is_zero() -> None:
    assert (
        _line({"trading": {"stream_down_s": None, "skew_ms": None}}).stream_down_s
        is None
    )
    assert _line({"trading": {"stream_down_s": 0, "skew_ms": 4}}).stream_down_s == 0


def test_a_section_that_did_not_answer_leaves_its_fields_unknown() -> None:
    gone = {STATUS_KEY: UNAVAILABLE, "reason": "timed out"}

    line = _line({"bots": gone, "market_data": gone, "trading": gone})

    assert line.bots == ()
    assert (line.tick_age_s, line.stream_down_s, line.skew_ms) == (None, None, None)


def test_a_value_of_the_wrong_kind_is_unknown_not_guessed() -> None:
    line = _line({"market_data": {"tick_age_s": "soon"}, "trading": {"skew_ms": True}})

    assert line.tick_age_s is None
    assert line.skew_ms is None


def test_a_snapshot_written_before_the_start_does_not_give_a_negative_uptime() -> None:
    snapshot = snapshot_aged(0, {})
    earlier = snapshot.started_at + timedelta(days=1)
    clock_went_back = type(snapshot)(
        app_version=snapshot.app_version,
        pid=snapshot.pid,
        started_at=earlier,
        written_at=snapshot.written_at,
        interval_s=snapshot.interval_s,
        host_state=snapshot.host_state,
        sections=snapshot.sections,
    )

    assert health_line_of(clock_went_back, None).up_s == 0


def test_the_whole_line_survives_the_format_and_the_parser() -> None:
    line = _line({"bots": _BOTS, "market_data": _MARKET, "trading": _TRADING})

    assert parse_health_line(format_health_line(line)) == line
