"""The line the host logs after each snapshot (`EPIC-038D`)."""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line import (
    BotCount,
    health_lines_in,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_line_logger import (
    HealthLineLogger,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_process_memory import (
    IProcessMemory,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.status_world import (
    snapshot_aged,
)


class _Memory(IProcessMemory):
    def __init__(self, resident: int | None) -> None:
        self._resident = resident

    def resident_mb(self) -> int | None:
        return self._resident


def _log(
    caplog: pytest.LogCaptureFixture,
    sections: dict[str, dict[str, object]],
    resident: int | None = 310,
) -> str:
    with caplog.at_level(logging.DEBUG, logger="App.Operations"):
        HealthLineLogger(_Memory(resident))(snapshot_aged(0, sections))  # type: ignore[arg-type]
    (record,) = [r for r in caplog.records if "[health]" in r.getMessage()]
    assert record.levelno == logging.INFO, (
        "the health line is INFO, never raised by its caller"
    )
    assert record.name == "App.Operations"
    # The app's own record format (`logging-rule.md` §8), which the parser reads.
    return f"2026-10-13 09:00:00,000 - {record.name} - INFO - {record.getMessage()}"


def test_the_health_line_is_parseable_and_reports_a_stale_feed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    text = _log(
        caplog,
        {
            "bots": {"states": {"RUNNING": 2, "PAUSED": 1}},
            "market_data": {"tick_age_s": 1800},
            "trading": {"stream_down_s": 0, "skew_ms": 15},
        },
    )

    (line,) = health_lines_in(text)

    assert line.tick_age_s == 1800  # a stale feed is a large age, not a hidden one
    assert line.stream_down_s == 0
    assert line.skew_ms == 15
    assert line.rss_mb == 310
    assert (line.bots[0], line.bots[1]) == (
        BotCount("running", 2),
        BotCount("paused", 1),
    )


def test_a_memory_that_cannot_be_read_is_na_on_the_line(
    caplog: pytest.LogCaptureFixture,
) -> None:
    text = _log(caplog, {"bots": {"states": {}}}, resident=None)

    assert health_lines_in(text)[0].rss_mb is None
    assert "rss_mb=na" in text
