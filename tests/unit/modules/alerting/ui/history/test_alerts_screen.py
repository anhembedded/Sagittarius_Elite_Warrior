"""`EPIC-036D2` — the Alerts screen tells the owner what was sent and whether a channel is
failing, in words."""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.alert_history_report import (
    AlertHistoryReport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_history import (
    IAlertHistory,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history import history_words
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.history.alerts_world import (
    AlertsScreen,
    build_screen,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    an_alert,
    bot_subject,
)


@pytest.fixture
def screen(qapp, request, tmp_path: Path) -> AlertsScreen:
    return build_screen(request, tmp_path)


def _raise(screen: AlertsScreen, kind: AlertKind, bot: str = "g3n092") -> None:
    screen.rig.hub.publish(an_alert(kind, bot_subject(bot)))
    screen.rig.deliver_all()


def test_a_sent_alert_is_listed_in_words(screen: AlertsScreen) -> None:
    _raise(screen, AlertKind.BOT_HALTED)

    screen.refresh()

    assert screen.view.shown_count == 1
    assert screen.cell(0, "severity") == "Critical"
    assert screen.cell(0, "subject") == "bot g3n092"
    assert screen.cell(0, "alert") == "BOT_HALTED title"
    assert screen.cell(0, "delivery") == "Discord: delivered"
    assert "Discord: working" in screen.view.channels_text
    assert screen.view.notice_text == ""


def test_an_alert_nobody_received_says_so(qapp, request, tmp_path: Path) -> None:
    screen = build_screen(request, tmp_path, channel_ids=())
    screen.rig.hub.publish(an_alert(AlertKind.BOT_HALTED))

    screen.refresh()

    assert screen.cell(0, "delivery") == history_words.NOT_SENT
    assert screen.view.channels_text == history_words.NO_CHANNELS


def test_a_failing_channel_gets_a_notice_that_names_it(screen: AlertsScreen) -> None:
    screen.rig.channels["discord"].script.append(DeliveryResult.refused("refused"))
    _raise(screen, AlertKind.BOT_HALTED)

    screen.refresh()

    deliveries = [
        screen.cell(row, "delivery") for row in range(screen.view.shown_count)
    ]
    assert "Discord: failed ×1" in deliveries
    assert "Discord: failing" in screen.view.channels_text
    assert screen.view.notice_text.startswith("Discord is not getting your alerts")


def test_the_notice_goes_when_the_channel_recovers(screen: AlertsScreen) -> None:
    screen.rig.channels["discord"].script.append(DeliveryResult.refused("refused"))
    _raise(screen, AlertKind.BOT_HALTED, "aaaaaa")
    screen.refresh()
    assert screen.view.notice_text

    _raise(screen, AlertKind.BOT_HALTED, "bbbbbb")
    screen.refresh()

    assert screen.view.notice_text == ""


def test_the_filter_narrows_what_is_shown_without_reading_again(
    screen: AlertsScreen,
) -> None:
    _raise(screen, AlertKind.BOT_HALTED, "aaaaaa")
    screen.rig.clock.advance(timedelta(minutes=20))
    _raise(screen, AlertKind.ORDER_FILLED, "bbbbbb")
    screen.refresh()
    assert screen.view.shown_count == 2

    screen.choose(history_words.FILTER_CRITICAL)

    assert screen.view.shown_count == 1
    assert screen.cell(0, "severity") == "Critical"
    screen.choose(history_words.FILTER_ALL)
    assert screen.view.shown_count == 2


class _Failing(IAlertHistory):
    def __init__(self) -> None:
        self.fail = False

    def read(self, limit: int) -> AlertHistoryReport:
        if self.fail:
            raise RuntimeError("secret detail the screen must not show")
        return AlertHistoryReport((), ())


def test_a_failed_read_is_told_by_type_and_keeps_the_screen_alive(
    qapp, request, tmp_path: Path
) -> None:
    history = _Failing()
    screen = build_screen(request, tmp_path, history=history)
    history.fail = True

    screen.refresh()

    assert "RuntimeError" in screen.view.history_note
    assert "secret detail" not in screen.view.history_note
    history.fail = False
    screen.refresh()
    assert screen.view.history_note == ""


def test_a_read_in_flight_is_not_asked_twice(screen: AlertsScreen) -> None:
    screen.threads.held = []

    screen.presenter.refresh()
    screen.presenter.refresh()

    assert len(screen.threads.held) == 1


def test_an_answer_after_shutdown_is_dropped(screen: AlertsScreen) -> None:
    _raise(screen, AlertKind.BOT_HALTED)
    screen.threads.held = []
    screen.presenter.refresh()

    screen.presenter.shutdown()
    for release in screen.threads.held:
        release()

    assert screen.view.shown_count == 0


def test_an_answer_for_a_read_that_is_no_longer_current_is_dropped(
    screen: AlertsScreen,
) -> None:
    """The fence (`async-ui-action-rule.md`): the relay still delivers, but the id is stale."""
    _raise(screen, AlertKind.BOT_HALTED)
    report = screen.rig.outbox.history(10)
    assert report
    screen.threads.held = []
    screen.presenter.refresh()
    stale_id = 0

    screen.presenter._on_read_done((stale_id, AlertHistoryReport((), ()), None))

    assert screen.view.shown_count == 0
    assert screen.view.history_note == history_words.READING


class _Counting(IAlertHistory):
    def __init__(self) -> None:
        self.reads = 0

    def read(self, limit: int) -> AlertHistoryReport:
        self.reads += 1
        return AlertHistoryReport((), ())


def test_nothing_is_read_until_the_mode_is_shown_and_nothing_while_it_is_hidden(
    qapp, request, tmp_path: Path
) -> None:
    """Every mode is built at start; a hidden Alerts mode must not query the outbox."""
    history = _Counting()
    screen = build_screen(request, tmp_path, history=history)
    assert history.reads == 0

    screen.presenter.on_mode_shown(NavigationSource.USER_INTENT)
    assert history.reads == 1
    assert screen.presenter._timer.isActive()

    screen.presenter._refresh_if_visible()
    assert history.reads == 1, "a tick reads nothing while the view is not visible"
    screen.view.show()
    screen.presenter._refresh_if_visible()
    assert history.reads == 2
