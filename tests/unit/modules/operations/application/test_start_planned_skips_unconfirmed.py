"""`EPIC-045F` (ADR 045 D7) - `--start-planned` skips a planned mainnet bot the run did not confirm.

It used to refuse the whole run (exit 2, which systemd does not restart). The bot stays at rest, a
WARNING and one event tell a person how to start it, and the rest of the plan starts.
"""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.planned_bot_not_started_event import (
    PlannedBotNotStartedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.host_steps import (
    StartPlannedBots,
)
from Sagittarius_Elite_Warrior.tests.integration.golden.fakes.recording_event_publisher import (
    RecordingEventPublisher,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.operations.application.host_steps_world import (
    FixedPlan,
    StepsWorld,
    entry,
)

_LOGGER = "App.Operations.Host"


def _planned(
    plan: FixedPlan,
    world: StepsWorld,
    confirmed_venue: str | None = None,
    events: RecordingEventPublisher | None = None,
) -> StartPlannedBots:
    return StartPlannedBots(
        plan, world, confirmed_venue, events or RecordingEventPublisher()
    )


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.parametrize(
    ("typed", "skipped"),
    [
        (None, True),
        ("spot_testnet", True),
        ("futures_mainnet", True),
        ("spot_mainnet", False),
    ],
)
def test_a_planned_mainnet_bot_is_skipped_unless_its_venue_was_typed_and_the_rest_start(
    typed: str | None, skipped: bool, caplog: pytest.LogCaptureFixture
) -> None:
    """`EPIC-045F` (ADR 045 D7): this was a refusal of the whole start. It is now the one bot."""
    world = StepsWorld(
        entry("aaaaaa", "STOPPED", "spot_testnet"),
        entry("bbbbbb", "STOPPED", "spot_mainnet"),
    )
    events = RecordingEventPublisher()

    with caplog.at_level(logging.INFO, logger=_LOGGER):
        _planned(FixedPlan(frozenset({"aaaaaa", "bbbbbb"})), world, typed, events).run()

    started = [c.bot_id for c in world.starts]
    assert started == (["aaaaaa"] if skipped else ["aaaaaa", "bbbbbb"])
    assert len(events.events) == (1 if skipped else 0)
    if skipped:
        (event,) = events.events
        assert isinstance(event, PlannedBotNotStartedEvent)
        assert (event.bot_id, event.venue) == ("bbbbbb", "spot_mainnet")
        (warning,) = _warnings(caplog)
        assert "bbbbbb" in warning
        assert "`bot start bbbbbb --confirm-venue spot_mainnet`" in warning


def test_a_run_whose_every_planned_bot_is_unconfirmed_starts_none_and_is_not_an_error() -> (
    None
):
    world = StepsWorld(
        entry("aaaaaa", "STOPPED", "spot_mainnet"),
        entry("bbbbbb", "DRAFT", "futures_mainnet"),
    )
    events = RecordingEventPublisher()

    _planned(FixedPlan(frozenset({"aaaaaa", "bbbbbb"})), world, None, events).run()

    assert world.starts == []
    assert [e.bot_id for e in events.events] == ["aaaaaa", "bbbbbb"]  # type: ignore[attr-defined]


def test_a_mainnet_bot_the_plan_does_not_want_running_is_not_told() -> None:
    world = StepsWorld(entry("bbbbbb", "STOPPED", "spot_mainnet"))
    events = RecordingEventPublisher()

    _planned(FixedPlan(frozenset()), world, None, events).run()

    assert events.events == []


def test_a_mainnet_bot_already_running_is_left_alone_and_not_told() -> None:
    world = StepsWorld(entry("bbbbbb", "RUNNING", "spot_mainnet"))
    events = RecordingEventPublisher()

    _planned(FixedPlan(frozenset({"bbbbbb"})), world, None, events).run()

    assert world.starts == [] and events.events == []
