"""`EPIC-038G` — the health line is one stable, parseable format.

The host (`EPIC-038D`) logs one `[health] key=value …` line per interval; an
operator greps it, a monitor parses it, and the CI run-log scan reads the same
file. Nothing but the format function writes it, and nothing but the parser
reads it, so the two are tested as a pair: what one writes the other reads back,
and the literal text is pinned so a rename cannot slip through a round trip.
"""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line import (
    HEALTH_TAG,
    BotCount,
    HealthLine,
    HealthLineError,
    format_health_line,
    health_lines_in,
    log_health_line,
    parse_health_line,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_state import (
    HostState,
)

_SERVING = HealthLine(
    state=HostState.SERVING,
    up_s=3600,
    bots=(BotCount("running", 3), BotCount("paused", 1), BotCount("halted", 0)),
    tick_age_s=2,
    stream_down_s=5,
    skew_ms=-120,
    rss_mb=310,
)


def test_the_health_line_text_is_pinned() -> None:
    assert format_health_line(_SERVING) == (
        "[health] state=SERVING up=3600s bots=running:3,paused:1,halted:0 "
        "tick_age_s=2 stream_down_s=5 skew_ms=-120 rss_mb=310"
    )


def test_the_health_line_round_trips_through_its_parser() -> None:
    assert parse_health_line(format_health_line(_SERVING)) == _SERVING


def test_unknown_measurements_and_no_bots_round_trip() -> None:
    quiet = HealthLine(
        state=HostState.BOOTING,
        up_s=0,
        bots=(),
        tick_age_s=None,
        stream_down_s=None,
        skew_ms=None,
        rss_mb=None,
    )

    text = format_health_line(quiet)

    assert text == (
        "[health] state=BOOTING up=0s bots=none "
        "tick_age_s=na stream_down_s=na skew_ms=na rss_mb=na"
    )
    assert parse_health_line(text) == quiet


def test_the_parser_reads_a_whole_log_record() -> None:
    record = f"2026-10-12 10:00:00,123 - App.Operations - INFO - {format_health_line(_SERVING)}"

    assert parse_health_line(record) == _SERVING


def test_a_key_added_later_is_ignored_not_fatal() -> None:
    text = format_health_line(_SERVING) + " open_orders=4"

    assert parse_health_line(text) == _SERVING


@pytest.mark.parametrize(
    "text",
    [
        "no tag here state=SERVING",
        "[health] state=SERVING up=1s bots=none tick_age_s=na stream_down_s=na skew_ms=na",
        "[health] state=NAPPING up=1s bots=none tick_age_s=na stream_down_s=na skew_ms=na rss_mb=na",
        "[health] state=SERVING up=soon bots=none tick_age_s=na stream_down_s=na skew_ms=na rss_mb=na",
        "[health] state=SERVING up=1s bots=running tick_age_s=na stream_down_s=na skew_ms=na rss_mb=na",
        "[health] state=SERVING up=1s bots=none tick_age_s=na tick_age_s=3 stream_down_s=na skew_ms=na rss_mb=na",
        # The field's old name: it measured nothing the stream can report.
        "[health] state=SERVING up=1s bots=none tick_age_s=na stream_age_s=na skew_ms=na rss_mb=na",
    ],
)
def test_a_malformed_line_is_refused_not_guessed(text: str) -> None:
    with pytest.raises(HealthLineError):
        parse_health_line(text)


@pytest.mark.parametrize(
    "up",
    ["٣s", "9" * 5000 + "s", "1" * 19 + "s"],
    ids=["arabic-indic digit", "5000 digits", "19 digits"],
)
def test_a_number_that_is_not_a_plain_bounded_ascii_integer_is_refused_as_malformed(
    up: str,
) -> None:
    text = format_health_line(_SERVING).replace("up=3600s", f"up={up}")

    with pytest.raises(HealthLineError):
        parse_health_line(text)


@pytest.mark.parametrize(
    "field_overrides",
    [
        {"up_s": -1},
        {"tick_age_s": -1},
        {"rss_mb": -5},
        {"bots": (BotCount("running", 1), BotCount("running", 2))},
    ],
)
def test_a_health_line_that_could_not_be_parsed_back_cannot_be_built(
    field_overrides: dict[str, object],
) -> None:
    fields = {
        "state": _SERVING.state,
        "up_s": _SERVING.up_s,
        "bots": _SERVING.bots,
        "tick_age_s": _SERVING.tick_age_s,
        "stream_down_s": _SERVING.stream_down_s,
        "skew_ms": _SERVING.skew_ms,
        "rss_mb": _SERVING.rss_mb,
        **field_overrides,
    }

    with pytest.raises(HealthLineError):
        HealthLine(**fields)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("state", "count"), [("Running", 1), ("a=b", 1), ("", 1), ("running", -1)]
)
def test_a_bot_count_that_could_not_be_parsed_back_cannot_be_built(
    state: str, count: int
) -> None:
    with pytest.raises(HealthLineError):
        BotCount(state, count)


def test_health_lines_are_found_among_other_records() -> None:
    log = "\n".join(
        [
            "2026-10-12 10:00:00,000 - App - INFO - App started.",
            f"2026-10-12 10:01:00,000 - App.Operations - INFO - {format_health_line(_SERVING)}",
            "2026-10-12 10:01:30,000 - App - INFO - Something else mentioning health.",
        ]
    )

    assert health_lines_in(log) == (_SERVING,)


def test_unrelated_records_mentioning_the_tag_are_skipped_not_fatal() -> None:
    log = "\n".join(
        [
            "2026-10-12 10:00:00,000 - App - INFO - user said [health] is fine",
            "2026-10-12 10:00:30,000 - App - INFO - [health] interval=60s",
            f"2026-10-12 10:01:00,000 - App.Operations - INFO - {format_health_line(_SERVING)}",
        ]
    )

    assert health_lines_in(log) == (_SERVING,)


def test_a_record_that_opens_like_a_health_line_but_is_malformed_still_raises() -> None:
    log = "2026-10-12 10:00:00,000 - App.Operations - INFO - [health] state=SERVING up=soon"

    with pytest.raises(HealthLineError):
        health_lines_in(log)


def test_a_stale_feed_is_logged_at_info_never_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Escalation belongs to the alert source; the CI log scan reads
    WARNING and above, so a health line must never trip it by itself."""
    stale = HealthLine(
        state=HostState.SERVING,
        up_s=90_000,
        bots=(BotCount("running", 1),),
        tick_age_s=86_400,
        stream_down_s=86_400,
        skew_ms=0,
        rss_mb=200,
    )
    logger = logging.getLogger("App.Operations.test_health_line")

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        log_health_line(logger, stale)

    assert [record.levelno for record in caplog.records] == [logging.INFO]
    assert caplog.records[0].getMessage().startswith(HEALTH_TAG)
