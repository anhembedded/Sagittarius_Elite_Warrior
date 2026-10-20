"""`BOT-190` — an exit that has closed the position becomes one INFO alert with the run's result.

`BotExitAlertSource` over a recording publisher: which exits are told, what the message says, and
that each run is its own message.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_exit_alert_source import (
    BotExitAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.recording_alert_publisher import (
    RecordingAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_exit_closed_event import (
    BotExitClosedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    BOT,
    Bots,
    entry,
)


def _event(
    reason: GridReason = GridReason.STOP_LOSS,
    run_id: str = "run-1",
    total_pnl: Decimal | None = Decimal("-35.23"),
) -> BotExitClosedEvent:
    return BotExitClosedEvent(
        bot_id=BOT,
        run_id=run_id,
        reason=reason.value,
        total_pnl=total_pnl,
        grid_profit=Decimal("12.50"),
        completed_cycles=7,
        unpriced_fees=0,
        quote_asset="USDT",
    )


def _source(
    bots: Bots | None = None,
) -> tuple[BotExitAlertSource, RecordingAlertPublisher]:
    published = RecordingAlertPublisher()
    source = BotExitAlertSource(bots or Bots(entry()), published, FakeAlertClock())
    return source, published


@pytest.mark.parametrize(
    ("reason", "name"),
    [
        (GridReason.STOP_LOSS, "The stop loss"),
        (GridReason.TAKE_PROFIT, "The take profit"),
        (GridReason.RANGE_EXIT, "The range exit"),
    ],
)
def test_an_exit_that_closed_the_position_is_one_info_alert_with_the_runs_result(
    reason: GridReason, name: str
) -> None:
    source, published = _source()

    source.on_exit_closed(_event(reason))

    [alert] = published.published
    assert (alert.kind, alert.severity) == (AlertKind.EXIT_CLOSED, Severity.INFO)
    assert name in alert.detail
    assert "-35.23" in alert.detail
    assert "12.50" in alert.detail
    assert "7 cycle(s)" in alert.detail
    assert alert.subject.bot_id == BOT


@pytest.mark.parametrize(
    "reason",
    [GridReason.USER_STOP, GridReason.SWITCH_OFF, GridReason.PROTECTIVE_STOP_TRIGGERED],
)
def test_a_stop_that_is_not_one_of_the_three_exits_tells_no_result(
    reason: GridReason,
) -> None:
    source, published = _source()

    source.on_exit_closed(_event(reason))

    assert published.published == []


def test_a_result_that_cannot_be_judged_is_said_so_never_zero() -> None:
    source, published = _source()

    source.on_exit_closed(_event(total_pnl=None))

    [alert] = published.published
    assert "The run's result: no price yet." in alert.detail


def test_each_run_is_its_own_message_and_a_repeat_of_one_event_is_the_same_key() -> (
    None
):
    source, published = _source()

    source.on_exit_closed(_event(run_id="run-1"))
    source.on_exit_closed(_event(run_id="run-1"))
    source.on_exit_closed(_event(run_id="run-2"))

    first, repeat, second = published.published
    assert first.dedup_key == repeat.dedup_key
    assert first.dedup_key != second.dedup_key


def test_a_bot_the_report_no_longer_lists_is_still_told_by_its_id() -> None:
    source, published = _source(Bots())

    source.on_exit_closed(_event())

    [alert] = published.published
    assert alert.subject.bot_id == BOT
