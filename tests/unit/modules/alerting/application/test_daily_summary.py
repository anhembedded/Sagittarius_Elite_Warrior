"""`EPIC-036E` - the daily summary: once a day, whole, exact, and never late after a restart."""

from __future__ import annotations

from dataclasses import replace
from datetime import time
from decimal import Decimal
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.heartbeat_text import (
    MAX_DETAIL,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.quiet_hours import QuietHours
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusReport,
    UnreadableBotEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    RunEarnings,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.heartbeat_world import (
    at,
    beats_of,
    service_of,
    start_at,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    Bots,
    entry,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    an_alert,
    build_rig,
)


def test_the_summary_is_sent_once_a_day_after_its_time_and_not_before(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    service = service_of(rig, Bots(entry()))
    start_at(rig, at(0, 30, day_offset=1))
    service.tick()
    assert beats_of(rig, AlertKind.DAILY_SUMMARY) == []

    start_at(rig, at(1, 0, day_offset=1))
    service.tick()
    service.tick()
    assert len(beats_of(rig, AlertKind.DAILY_SUMMARY)) == 1

    start_at(rig, at(23, 0, day_offset=1))
    service.tick()
    assert len(beats_of(rig, AlertKind.DAILY_SUMMARY)) == 1

    start_at(rig, at(1, 5, day_offset=2))
    service.tick()
    assert len(beats_of(rig, AlertKind.DAILY_SUMMARY)) == 2


def test_an_app_started_after_the_summary_time_sends_no_summary_that_day(
    tmp_path: Path,
) -> None:
    """A missed summary is not sent late, and a restart cannot send one twice."""
    rig = build_rig(tmp_path)
    start_at(rig, at(14, 0, day_offset=1))
    service = service_of(rig, Bots(entry()))
    service.tick()
    service_of(rig, Bots(entry())).tick()

    assert beats_of(rig, AlertKind.DAILY_SUMMARY) == []

    start_at(rig, at(1, 0, day_offset=2))
    service.tick()
    assert len(beats_of(rig, AlertKind.DAILY_SUMMARY)) == 1


def test_a_restart_after_the_summary_was_sent_does_not_send_it_again(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    start_at(rig, at(0, 30, day_offset=1))
    first = service_of(rig, Bots(entry()))
    first.tick()
    start_at(rig, at(1, 0, day_offset=1))
    first.tick()

    service_of(rig, Bots(entry())).tick()

    assert len(beats_of(rig, AlertKind.DAILY_SUMMARY)) == 1


def test_the_summary_counts_bots_by_state_and_the_alerts_of_the_last_day(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    earned = replace(
        entry("RUNNING"),
        earnings=RunEarnings(
            grid_profit=Decimal("12.50"),
            completed_cycles=7,
            total_pnl=Decimal("9.75"),
            judged=True,
        ),
    )
    halted = replace(entry("HALTED", "rate_limited"), bot_id="h1", name="sol-grid")
    service = service_of(rig, Bots(earned, halted))
    start_at(rig, at(0, 30, day_offset=1))
    service.tick()
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED, at=rig.clock.now()))
    start_at(rig, at(1, 0, day_offset=1))
    service.tick()

    [text] = beats_of(rig, AlertKind.DAILY_SUMMARY)

    assert "1 RUNNING" in text
    assert "1 HALTED" in text
    assert "12.50" in text
    assert "9.75" in text
    assert "BOT_HALTED" in text


def test_the_daily_summary_and_the_quiet_hours_digest_do_not_share_a_condition(
    tmp_path: Path,
) -> None:
    """The digest of held alerts is a `DAILY_SUMMARY` too; its key carries the instant it
    was released, the daily one the date, so neither swallows the other."""
    rig = build_rig(tmp_path)
    service = service_of(rig, Bots(entry()))
    start_at(rig, at(0, 30, day_offset=1))
    service.tick()
    start_at(rig, at(1, 0, day_offset=1))
    service.tick()

    keys = {
        e.record.alert.dedup_key
        for e in rig.outbox.history(50)
        if e.record.alert.kind is AlertKind.DAILY_SUMMARY
    }

    assert keys == {f"DAILY_SUMMARY:app:daily-{rig.clock.now():%Y-%m-%d}"}


def test_the_summary_keeps_its_alert_counts_and_unreadable_warning_at_any_number_of_bots(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    earned = RunEarnings(
        grid_profit=Decimal("12.345678"),
        completed_cycles=123,
        total_pnl=Decimal("-3.21456789"),
        judged=True,
    )
    bots = [
        replace(
            entry("RUNNING"), bot_id=f"b{n}", name=f"grid-bot-{n:02d}", earnings=earned
        )
        for n in range(60)
    ]
    report = BotStatusReport(
        bots=tuple(bots),
        unreadable=(UnreadableBotEntry("x", "/tmp/x.json", "bad"),),
    )

    class _Report(ICommandDispatcher):
        def dispatch(
            self, handler_class: type, input_dto: object | None = None
        ) -> object:
            return report

    service = service_of(rig, _Report())
    start_at(rig, at(0, 30, day_offset=1))
    service.tick()
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED, at=rig.clock.now()))
    start_at(rig, at(1, 0, day_offset=1))
    service.tick()
    [text] = beats_of(rig, AlertKind.DAILY_SUMMARY)

    assert len(text) <= MAX_DETAIL
    assert "1 bot file(s) could not be read." in text
    assert "BOT_HALTED x1" in text


def test_the_summarys_alert_counts_are_exact_beyond_five_hundred_alerts(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    service = service_of(rig, Bots(entry()))
    start_at(rig, at(0, 30, day_offset=1))
    service.tick()
    for number in range(600):
        rig.outbox.enqueue(
            an_alert(AlertKind.ORDER_FILLED, at=rig.clock.now(), reason=str(number)),
            (),
            rig.clock.now(),
        )
    start_at(rig, at(1, 0, day_offset=1))
    service.tick()

    [text] = beats_of(rig, AlertKind.DAILY_SUMMARY)

    assert "ORDER_FILLED x600" in text


def test_a_summary_inside_quiet_hours_still_arrives_whole(tmp_path: Path) -> None:
    """Held, it would reach the owner as a title in the digest of held alerts."""
    rig = build_rig(tmp_path)
    rig.settings.replace(AlertSettings(quiet_hours=QuietHours(time(22, 0), time(9, 0))))
    service = service_of(rig, Bots(entry()))
    start_at(rig, at(0, 30, day_offset=1))
    service.tick()
    start_at(rig, at(1, 0, day_offset=1))
    service.tick()
    rig.deliver_all()

    for channel in rig.channels.values():
        kinds = [r.alert.kind for r in channel.received]
        assert AlertKind.DAILY_SUMMARY in kinds
        [summary] = [
            r.alert for r in channel.received if r.alert.kind is AlertKind.DAILY_SUMMARY
        ]
        assert "1 bot(s)" in summary.detail
