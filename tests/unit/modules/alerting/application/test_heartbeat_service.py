"""`EPIC-036E` - the owner hears from the bots on a schedule: a heartbeat and a daily summary.

The service is the real one over a real hub and outbox (`world.build_rig`); only the channels,
the clock and the bots' status report are fakes.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, time, timedelta
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.heartbeat_service import (
    HeartbeatService,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.heartbeat_text import (
    MAX_DETAIL,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_publisher import (
    IAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.quiet_hours import QuietHours
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.heartbeat_world import (
    EVERY,
    POLICY,
    beats_of,
    service_of,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    Bots,
    entry,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    NOW,
    an_alert,
    build_rig,
)


def test_a_heartbeat_is_sent_at_the_first_tick_and_then_only_each_interval(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    service = service_of(rig, Bots(entry()))

    service.tick()
    rig.clock.advance(EVERY - timedelta(seconds=1))
    service.tick()
    assert len(beats_of(rig)) == 1

    rig.clock.advance(timedelta(seconds=1))
    service.tick()
    assert len(beats_of(rig)) == 2


def test_a_restart_does_not_send_a_second_heartbeat_inside_the_interval(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    service_of(rig, Bots(entry())).tick()
    rig.clock.advance(timedelta(minutes=10))

    service_of(rig, Bots(entry())).tick()

    assert len(beats_of(rig)) == 1


def test_the_heartbeat_lists_each_bots_state_reason_and_resting_orders(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    halted = replace(entry("HALTED", "user_stream_down"), resting_orders=4)
    running = replace(entry("RUNNING"), bot_id="r1", name="btc-grid", symbol="BTCUSDT")
    service_of(rig, Bots(halted, running)).tick()

    [text] = beats_of(rig)

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
    service_of(rig, Bots(with_health)).tick()

    [text] = beats_of(rig)

    assert "feed_age_s=3" in text
    assert "stream=connected" in text


def test_a_bot_with_no_health_snapshot_yet_shows_no_invented_figures(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    service_of(rig, Bots(entry("RUNNING"))).tick()

    [text] = beats_of(rig)

    assert "feed" not in text.lower()


def test_no_bots_is_said_in_words(tmp_path: Path) -> None:
    rig = build_rig(tmp_path)
    service_of(rig, Bots()).tick()

    [text] = beats_of(rig)

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

    service_of(rig, _Broken()).tick()

    [text] = beats_of(rig)
    assert "could not be read" in text
    assert "RuntimeError" in text


def test_the_heartbeat_is_a_silent_info_message_on_every_channel(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    service_of(rig, Bots(entry())).tick()
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
    service_of(rig, Bots(entry())).tick()
    rig.deliver_all()

    assert all(not channel.received for channel in rig.channels.values())


def test_a_tick_that_fails_never_raises_and_says_why_in_the_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    class _FailingPublisher(IAlertPublisher):
        def publish(self, alert: Alert) -> None:
            raise MemoryError("the outbox is gone")

        def condition_cleared(self, dedup_key: str, at: datetime) -> None:
            raise MemoryError("the outbox is gone")

    rig = build_rig(tmp_path)
    service = HeartbeatService(
        Bots(entry()),
        _FailingPublisher(),
        rig.outbox,
        rig.clock,
        rig.settings,
        POLICY,
    )

    with caplog.at_level(logging.WARNING, logger="App.Alerting"):
        service.tick()

    assert any(
        "pass failed" in record.getMessage() and record.exc_info
        for record in caplog.records
    )


def test_an_unreadable_report_is_in_the_run_log_with_its_traceback(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The message tells the owner to see the run log, so the run log must hold the error."""

    class _Broken(ICommandDispatcher):
        def dispatch(
            self, handler_class: type, input_dto: object | None = None
        ) -> object:
            raise RuntimeError("the bot store is locked")

    rig = build_rig(tmp_path)

    with caplog.at_level(logging.WARNING, logger="App.Alerting"):
        service_of(rig, _Broken()).tick()

    [record] = [r for r in caplog.records if "could not be read" in r.getMessage()]
    assert record.exc_info is not None
    assert "the bot store is locked" in str(record.exc_info[1])


def test_the_lines_that_matter_come_first_and_the_whole_fits_what_discord_takes(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path)
    bots = [
        replace(entry("RUNNING"), bot_id=f"b{n}", name=f"grid-bot-{n:02d}")
        for n in range(60)
    ]
    service = service_of(rig, Bots(*bots))

    service.tick()
    [text] = beats_of(rig)

    assert len(text) <= MAX_DETAIL
    assert text.splitlines()[1].startswith("60 bot(s)")
    assert "... and " in text.splitlines()[-1]


def test_a_restart_after_a_busy_stretch_still_sees_the_last_heartbeat(
    tmp_path: Path,
) -> None:
    """Fills are rows of their own: more than five hundred of them after the heartbeat must not
    push it out of what a restart can find."""
    rig = build_rig(tmp_path)
    service_of(rig, Bots(entry())).tick()
    for number in range(600):
        rig.outbox.enqueue(
            an_alert(AlertKind.ORDER_FILLED, at=rig.clock.now(), reason=str(number)),
            (),
            rig.clock.now(),
        )
    rig.clock.advance(timedelta(minutes=10))

    service_of(rig, Bots(entry())).tick()

    counts = rig.outbox.alert_counts_since(NOW - timedelta(days=1))
    assert counts[AlertKind.HEARTBEAT] == 1


def test_an_interval_the_owner_chose_replaces_the_policys_and_applies_at_the_next_tick(
    tmp_path: Path,
) -> None:
    """`EPIC-036D9`: shorter, then longer, with no restart between."""
    rig = build_rig(tmp_path)
    service = service_of(rig, Bots(entry()))
    service.tick()
    rig.settings.replace(AlertSettings(heartbeat_every=timedelta(hours=1)))

    rig.clock.advance(timedelta(hours=1))
    service.tick()
    assert len(beats_of(rig)) == 2

    rig.settings.replace(AlertSettings(heartbeat_every=timedelta(hours=12)))
    rig.clock.advance(EVERY)
    service.tick()
    assert len(beats_of(rig)) == 2

    rig.clock.advance(EVERY)
    service.tick()
    assert len(beats_of(rig)) == 3


def test_with_no_interval_chosen_the_policys_applies(tmp_path: Path) -> None:
    rig = build_rig(tmp_path)
    rig.settings.replace(AlertSettings(heartbeat_every=None))
    service = service_of(rig, Bots(entry()))
    service.tick()

    rig.clock.advance(EVERY - timedelta(seconds=1))
    service.tick()
    assert len(beats_of(rig)) == 1

    rig.clock.advance(timedelta(seconds=1))
    service.tick()
    assert len(beats_of(rig)) == 2
