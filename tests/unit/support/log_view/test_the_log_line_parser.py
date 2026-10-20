"""Every real shape of a log line is read, and no other line is ever an error (`BOT-199`)."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.support.log_view.log_line import (
    level_number,
    parse_head,
)
from Sagittarius_Elite_Warrior.tests.unit.support.log_view import (
    log_view_samples as samples,
)


@pytest.mark.parametrize(
    ("line", "logger", "level"),
    [
        (samples.EXIT_SLICE, "App.Bots.GridExit", "INFO"),
        (samples.HEALTH, "App.Operations.Health", "INFO"),
        (samples.BOOT_RECOVERY, "App.Bots.Recovery", "WARNING"),
        (samples.ERROR_HEAD, "App.Shell", "ERROR"),
        (samples.DEBUG_LINE, "App.Chart", "DEBUG"),
    ],
)
def test_a_record_head_is_cut_at_its_three_separators(
    line: str, logger: str, level: str
) -> None:
    head = parse_head(line)

    assert head is not None
    assert (head.logger, head.level) == (logger, level)
    assert head.body[head.message_start :] == head.message
    assert head.timestamp == line[:23]


@pytest.mark.parametrize(
    "line",
    [
        samples.NOT_A_RECORD,
        samples.TRACEBACK[0],
        "",
        "2026-10-20 02:00:01 - missing millis - INFO - x",
        "2026-10-20 02:00:01,123 - App.X - INFO -",
        "\x00\x01 binary �",
    ],
)
def test_a_line_that_is_not_a_record_head_is_none_and_never_raises(line: str) -> None:
    assert parse_head(line) is None


def test_a_level_is_a_number_and_an_unknown_one_is_none() -> None:
    assert level_number("TRACE") == 5
    assert level_number("WARNING") == 30
    assert level_number("Level 7") == 7
    assert level_number("FATAL") is None
