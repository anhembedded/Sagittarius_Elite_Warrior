"""`--level`, `--bot`, `--tag` and `--since` keep or drop a record with its continuation lines."""

from __future__ import annotations

import io
from datetime import datetime

import pytest
from Sagittarius_Elite_Warrior.src.support.log_view.log_filter import (
    FilterError,
    LogFilter,
    parse_level,
    parse_since,
    parse_tag,
)
from Sagittarius_Elite_Warrior.src.support.log_view.log_renderers_plain import (
    PlainRenderer,
)
from Sagittarius_Elite_Warrior.src.support.log_view.log_viewer import LogViewer
from Sagittarius_Elite_Warrior.src.support.log_view.template_matcher import (
    TemplateMatcher,
)
from Sagittarius_Elite_Warrior.tests.unit.support.log_view import (
    log_view_samples as samples,
)

_NOW = datetime(2026, 10, 20, 12, 0, 0).astimezone()
_LOG = [
    samples.DEBUG_LINE,
    samples.EXIT_SLICE,
    samples.BOOT_RECOVERY,
    samples.ERROR_HEAD,
    *samples.TRACEBACK,
    samples.UNTAGGED,
]


def _shown(log_filter: LogFilter, lines: list[str]) -> list[str]:
    out = io.StringIO()
    viewer = LogViewer(PlainRenderer(out), TemplateMatcher(()), log_filter)
    viewer.feed_all(line + "\n" for line in lines)
    return out.getvalue().splitlines()


def test_no_filter_shows_every_line_unchanged() -> None:
    assert _shown(LogFilter(), [samples.NOT_A_RECORD, *_LOG]) == [
        samples.NOT_A_RECORD,
        *_LOG,
    ]


def test_level_keeps_that_level_and_above_and_the_traceback_goes_with_its_record() -> (
    None
):
    shown = _shown(LogFilter(min_level=parse_level("warning")), _LOG)

    assert shown == [samples.BOOT_RECOVERY, samples.ERROR_HEAD, *samples.TRACEBACK]


def test_a_dropped_record_drops_its_traceback_too() -> None:
    shown = _shown(LogFilter(min_level=parse_level("critical")), _LOG)

    assert shown == []


def test_bot_keeps_records_naming_that_id_as_a_whole_word() -> None:
    assert _shown(LogFilter(bot="uie03d"), _LOG) == [
        samples.EXIT_SLICE,
        samples.BOOT_RECOVERY,
    ]
    assert _shown(LogFilter(bot="uie03"), _LOG) == []


def test_tag_keeps_records_with_that_bracket_tag() -> None:
    assert _shown(LogFilter(tag=parse_tag("[boot-recovery]")), _LOG) == [
        samples.BOOT_RECOVERY
    ]
    assert _shown(LogFilter(tag="boot-recovery"), _LOG) == [samples.BOOT_RECOVERY]


def test_since_drops_the_records_before_it_and_a_line_that_is_not_a_record() -> None:
    log_filter = LogFilter(since=parse_since("2026-10-20T02:00:04", _NOW))

    shown = _shown(log_filter, [samples.NOT_A_RECORD, *_LOG])

    assert shown == [samples.ERROR_HEAD, *samples.TRACEBACK, samples.UNTAGGED]


def test_filters_combine() -> None:
    log_filter = LogFilter(min_level=parse_level("warn"), bot="uie03d")

    assert _shown(log_filter, _LOG) == [samples.BOOT_RECOVERY]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2h", "2026-10-20T10:00:00"),
        ("30m", "2026-10-20T11:30:00"),
        ("1d12h", "2026-10-19T00:00:00"),
        ("today", "2026-10-20T00:00:00"),
        ("yesterday", "2026-10-19T00:00:00"),
        ("2026-10-20T14:30", "2026-10-20T14:30:00"),
    ],
)
def test_since_reads_relative_words_and_iso_times(text: str, expected: str) -> None:
    assert parse_since(text, _NOW) == datetime.fromisoformat(expected).astimezone()


@pytest.mark.parametrize("text", ["", "soon", "2 hours ago", "h2"])
def test_a_since_that_is_not_understood_is_a_filter_error(text: str) -> None:
    with pytest.raises(FilterError):
        parse_since(text, _NOW)


def test_an_unknown_level_is_a_filter_error_that_names_the_choices() -> None:
    with pytest.raises(
        FilterError, match="trace, debug, info, warning, error, critical"
    ):
        parse_level("loud")
