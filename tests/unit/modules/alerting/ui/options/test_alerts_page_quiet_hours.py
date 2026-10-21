"""`EPIC-036D6` — Tools → Options → Alerts: the Quiet hours group.

The page, the setup and the settings file (`JsonAlertSettings` under `tmp_path`) are the real
ones. Save acts at once, like the page's other buttons; the check box is what the group means:
checked and Save keeps the period, cleared and Save turns it off.
"""

from __future__ import annotations

import os
from datetime import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTime
from PySide6.QtWidgets import QCheckBox, QTimeEdit
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_quiet_hours_setting import (
    QuietHoursChoice,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.options.alerts_page_world import (
    STATUS,
    AlertsPage,
    build_page,
)

SAVE = "btnSaveQuietHours"
STATE = "lblQuietHoursState"


@pytest.fixture
def page(qapp, request, monkeypatch) -> AlertsPage:
    return build_page(request, monkeypatch)


def _enable(page: AlertsPage, on: bool) -> None:
    page.view.findChild(QCheckBox, "chkQuietHours").setChecked(on)


def _times(page: AlertsPage, start: QTime, end: QTime) -> None:
    page.view.findChild(QTimeEdit, "timQuietFrom").setTime(start)
    page.view.findChild(QTimeEdit, "timQuietTo").setTime(end)


def test_it_starts_off_with_a_night_in_the_boxes_and_the_zone_it_reads_in(
    page: AlertsPage,
) -> None:
    assert not page.view.findChild(QCheckBox, "chkQuietHours").isChecked()
    assert page.view.findChild(QTimeEdit, "timQuietFrom").time() == QTime(22, 0)
    assert page.view.findChild(QTimeEdit, "timQuietTo").time() == QTime(7, 0)
    assert page.label(STATE) == "Off. Times are read in your display time zone (UTC)."
    assert not page.view.findChild(QTimeEdit, "timQuietFrom").isEnabled()


def test_checking_the_box_enables_the_times(page: AlertsPage) -> None:
    _enable(page, True)

    assert page.view.findChild(QTimeEdit, "timQuietFrom").isEnabled()
    assert page.view.findChild(QTimeEdit, "timQuietTo").isEnabled()


def test_save_keeps_the_period_and_the_line_says_what_is_held(
    page: AlertsPage,
) -> None:
    _enable(page, True)
    _times(page, QTime(23, 30), QTime(6, 15))

    page.click(SAVE)

    assert page.modes.quiet_hours() == QuietHoursChoice(
        time(23, 30), time(6, 15), "UTC"
    )
    assert page.label(STATE) == "Held from 23:30 to 06:15 (UTC)."
    assert page.label(STATUS) == "Quiet hours saved."


def test_save_with_the_box_cleared_turns_the_quiet_hours_off(page: AlertsPage) -> None:
    _enable(page, True)
    page.click(SAVE)
    assert page.modes.quiet_hours() is not None

    _enable(page, False)
    page.click(SAVE)

    assert page.modes.quiet_hours() is None
    assert page.label(STATE).startswith("Off.")
    assert page.label(STATUS) == "Quiet hours are off."


def test_the_same_time_twice_is_refused_in_words_and_nothing_is_kept(
    page: AlertsPage,
) -> None:
    _enable(page, True)
    _times(page, QTime(8, 0), QTime(8, 0))

    page.click(SAVE)

    assert page.modes.quiet_hours() is None
    assert "no quiet period" in page.label(STATUS)


def test_a_period_already_kept_is_shown_when_the_page_opens(
    qapp, request, monkeypatch, tmp_path
) -> None:
    modes = JsonAlertSettings(tmp_path / "state" / "alert_settings.json")
    modes.set_quiet_hours(QuietHoursChoice(time(21, 0), time(5, 0), "Europe/Berlin"))

    page = build_page(request, monkeypatch, modes=modes)

    assert page.view.findChild(QCheckBox, "chkQuietHours").isChecked()
    assert page.view.findChild(QTimeEdit, "timQuietFrom").time() == QTime(21, 0)
    assert page.label(STATE) == "Held from 21:00 to 05:00 (Europe/Berlin)."


def test_a_read_only_copy_offers_no_change_and_says_why(
    qapp, request, monkeypatch, tmp_path
) -> None:
    modes = JsonAlertSettings(
        tmp_path / "state" / "alert_settings.json", read_only=True
    )

    page = build_page(request, monkeypatch, modes=modes)

    assert not page.button(SAVE).isEnabled()
    assert not page.view.findChild(QCheckBox, "chkQuietHours").isEnabled()
    assert "read-only" in page.label(STATE)
    assert page.label(STATE).startswith("Off.")  # what is in force is still said


def test_the_save_button_is_off_while_the_work_is_out(page: AlertsPage) -> None:
    page.threads.held = []
    _enable(page, True)

    page.click(SAVE)
    assert not page.button(SAVE).isEnabled()

    page.threads.held[0]()
    assert page.button(SAVE).isEnabled()


def test_a_refused_period_stays_typed_in_the_boxes(page: AlertsPage) -> None:
    _enable(page, True)
    _times(page, QTime(8, 30), QTime(8, 30))

    page.click(SAVE)

    assert "no quiet period" in page.label(STATUS)
    assert page.view.findChild(QTimeEdit, "timQuietFrom").time() == QTime(8, 30)
    assert page.view.findChild(QCheckBox, "chkQuietHours").isChecked()
