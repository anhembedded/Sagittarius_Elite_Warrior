"""`BUG-201` — the UI integration app publishes its health snapshot without a complaint.

`app_engine` boots the composed GUI app and replaces the dispatcher's `dispatch`
with `mock_dispatch`. A writable boot also runs the health publisher, whose
`bots` contributor reads `GetBotStatusReportQuery` through that same dispatcher;
`mock_dispatch` answered it with a `_FakeResponse`, so the section raised
`AttributeError: _FakeResponse ... state_counts` and the collector logged a
WARNING on every publish, in every run of the conformance suite. It reached the
CI log scan only when a test in that file failed and pytest printed the log.

Retire when: the health publisher no longer reads through the dispatcher.
"""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_health_contributor import (
    IHealthContributors,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.health_cadence import (
    HealthCadence,
)


def test_one_publish_on_the_booted_app_logs_no_warning(
    app_engine, caplog: pytest.LogCaptureFixture
) -> None:
    cadence = app_engine.context.container.resolve(HealthCadence)

    with caplog.at_level(logging.WARNING):
        cadence.publish_now()

    complaints = [
        f"{record.name} {record.levelname}: {record.getMessage()}"
        for record in caplog.records
        if record.levelno >= logging.WARNING
    ]
    assert complaints == []


def test_the_bots_section_is_read_from_a_real_report_with_no_bot(app_engine) -> None:
    """Positive proof for the same fix: the section is answered, from a real
    `BotStatusReport`, not merely absent from the log."""
    contributors = app_engine.context.container.resolve(IHealthContributors)
    bots = next(c for c in contributors.contributors() if c.name == "bots")

    assert bots.snapshot()["total"] == 0
