"""`EPIC-036E` - the owner hears from the bots on a schedule: a heartbeat and a daily summary.

The service is the real one over a real hub and outbox (`world.build_rig`); only the channels,
the clock and the bots' status report are fakes.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.heartbeat_service import (
    HeartbeatService,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    HeartbeatPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.quiet_hours import QuietHours
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    RunEarnings,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    Bots,
    entry,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    NOW,
    Rig,
    an_alert,
    build_rig,
)

EVERY = timedelta(hours=6)
POLICY = HeartbeatPolicy(heartbeat_every=EVERY, summary_at=time(1, 0))


def _service(rig: Rig, bots: ICommandDispatcher) -> HeartbeatService:
    return HeartbeatService(bots, rig.hub, rig.outbox, rig.clock, POLICY)


def _beats(rig: Rig, kind: AlertKind = AlertKind.HEARTBEAT) -> list[str]:
    return [
        e.record.alert.detail
        for e in rig.outbox.history(500)
        if e.record.alert.kind is kind
    ]


def test_a_heartbeat_is_sent_at_the_first_tick_and_then_only_each_interval(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    service = _service(rig, Bots(entry()))

    service.tick()
    rig.clock.advance(EVERY - timedelta(seconds=1))
    service.tick()
    assert len(_beats(rig)) == 1

    rig.clock.advance(timedelta(seconds=1))
    service.tick()
    assert len(_beats(rig)) == 2


def test_a_restart_does_not_send_a_second_heartbeat_inside_the_interval(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    _service(rig, Bots(entry())).tick()
    rig.clock.advance(timedelta(minutes=10))

    _service(rig, Bots(entry())).tick()

    assert len(_beats(rig)) == 1


def test_the_heartbeat_lists_each_bots_state_reason_and_resting_orders(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    halted = replace(entry("HALTED", "user_stream_down"), resting_orders=4)
    running = replace(entry("RUNNING"), bot_id="r1", name="btc-grid", symbol="BTCUSDT")
    _service(rig, Bots(halted, running)).tick()

    [text] = _beats(rig)

    assert "eth-grid" in text
    assert "HALTED" in text
    assert "user_stream_down" in text
    assert "4 resting" in text
    assert "btc-grid" in text
    assert "RUNNING" in text


def test_the_heartbeat_prints_the_health_snapshot_verbatim_and_never_computes_one(
    tmp_path: Path,
) -> None:
    """`EPIC-035W` fills `health`; the message must show it unchanged so the screen and
    the message cannot disagree."""
    rig = build_rig(tmp_path)
    with_health = replace(
        entry("RUNNING"), health={"feed_age_s": 3, "stream": "connected"}
    )
    _service(rig, Bots(with_health)).tick()

    [text] = _beats(rig)

    assert "feed_age_s=3" in text
    assert "stream=connected" in text


def test_a_bot_with_no_health_snapshot_yet_shows_no_invented_figures(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    _service(rig, Bots(entry("RUNNING"))).tick()

    [text] = _beats(rig)

    assert "feed" not in text.lower()


def test_no_bots_is_said_in_words(tmp_path: Path) -> None:
    rig = build_rig(tmp_path)
    _service(rig, Bots()).tick()

    [text] = _beats(rig)

    assert "No bot" in text


def test_a_report_that_cannot_be_read_still_sends_a_heartbeat_that_says_so(
    tmp_path: Path,
) -> None:
    class _Broken(ICommandDispatcher):
        def dispatch(
            self, handler_class: type, input_dto: object | None = None
        ) -> object:
            raise RuntimeError("the bot store is locked")

    rig = build_rig(tmp_path)

    _service(rig, _Broken()).tick()

    [text] = _beats(rig)
    assert "could not be read" in text
    assert "RuntimeError" in text


def test_the_heartbeat_is_a_silent_info_message_on_every_channel(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    _service(rig, Bots(entry())).tick()
    rig.deliver_all()

    for channel in rig.channels.values():
        [received] = channel.received
        assert received.alert.kind is AlertKind.HEARTBEAT
        assert received.loudness is Loudness.SILENT


def test_a_heartbeat_inside_quiet_hours_waits_with_the_other_info_alerts(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    rig.settings.replace(
        AlertSettings(quiet_hours=QuietHours(time(11, 0), time(13, 0)))
    )
    _service(rig, Bots(entry())).tick()
    rig.deliver_all()

    assert all(not channel.received for channel in rig.channels.values())


def test_a_tick_that_fails_never_raises(tmp_path: Path) -> None:
    class _Raising(ICommandDispatcher):
        def dispatch(
            self, handler_class: type, input_dto: object | None = None
        ) -> object:
            raise MemoryError("not even this")

    rig = build_rig(tmp_path)
    service = _service(rig, _Raising())

    service.tick()


# -- the daily summary ------------------------------------------------------


def _at(hour: int, minute: int = 0, day_offset: int = 0) -> datetime:
    return datetime(NOW.year, NOW.month, NOW.day, hour, minute, tzinfo=UTC) + timedelta(
        days=day_offset
    )


def _start_at(rig: Rig, when: datetime) -> None:
    rig.clock.advance(when - rig.clock.now())


def test_the_summary_is_sent_once_a_day_after_its_time_and_not_before(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    service = _service(rig, Bots(entry()))
    _start_at(rig, _at(0, 30, day_offset=1))
    service.tick()
    assert _beats(rig, AlertKind.DAILY_SUMMARY) == []

    _start_at(rig, _at(1, 0, day_offset=1))
    service.tick()
    service.tick()
    assert len(_beats(rig, AlertKind.DAILY_SUMMARY)) == 1

    _start_at(rig, _at(23, 0, day_offset=1))
    service.tick()
    assert len(_beats(rig, AlertKind.DAILY_SUMMARY)) == 1

    _start_at(rig, _at(1, 5, day_offset=2))
    service.tick()
    assert len(_beats(rig, AlertKind.DAILY_SUMMARY)) == 2


def test_an_app_started_after_the_summary_time_sends_no_summary_that_day(
    tmp_path: Path,
) -> None:
    """A missed summary is not sent late, and a restart cannot send one twice."""
    rig = build_rig(tmp_path)
    _start_at(rig, _at(14, 0, day_offset=1))
    service = _service(rig, Bots(entry()))
    service.tick()
    _service(rig, Bots(entry())).tick()

    assert _beats(rig, AlertKind.DAILY_SUMMARY) == []

    _start_at(rig, _at(1, 0, day_offset=2))
    service.tick()
    assert len(_beats(rig, AlertKind.DAILY_SUMMARY)) == 1


def test_a_restart_after_the_summary_was_sent_does_not_send_it_again(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    _start_at(rig, _at(0, 30, day_offset=1))
    first = _service(rig, Bots(entry()))
    first.tick()
    _start_at(rig, _at(1, 0, day_offset=1))
    first.tick()

    _service(rig, Bots(entry())).tick()

    assert len(_beats(rig, AlertKind.DAILY_SUMMARY)) == 1


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
    service = _service(rig, Bots(earned, halted))
    _start_at(rig, _at(0, 30, day_offset=1))
    service.tick()
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED, at=rig.clock.now()))
    _start_at(rig, _at(1, 0, day_offset=1))
    service.tick()

    [text] = _beats(rig, AlertKind.DAILY_SUMMARY)

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
    service = _service(rig, Bots(entry()))
    _start_at(rig, _at(0, 30, day_offset=1))
    service.tick()
    _start_at(rig, _at(1, 0, day_offset=1))
    service.tick()

    keys = {
        e.record.alert.dedup_key
        for e in rig.outbox.history(50)
        if e.record.alert.kind is AlertKind.DAILY_SUMMARY
    }

    assert keys == {f"DAILY_SUMMARY:app:daily-{rig.clock.now():%Y-%m-%d}"}
