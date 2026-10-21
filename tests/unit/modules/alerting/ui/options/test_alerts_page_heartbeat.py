"""`EPIC-036D9` — Tools → Options → Alerts: the "Heartbeat" interval.

The page, `HeartbeatSetup`, and the settings file (`JsonAlertSettings` under `tmp_path`) are the
real ones. A choice acts at once, like the page's buttons."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import timedelta

from PySide6.QtWidgets import QComboBox
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    HEARTBEAT_HOURS_CHOICES,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.options.alerts_page_world import (
    STATUS,
    AlertsPage,
    build_page,
)


@pytest.fixture
def page(qapp, request, monkeypatch) -> AlertsPage:
    return build_page(request, monkeypatch, running=True)


def _combo(page: AlertsPage) -> QComboBox:
    box = page.view.findChild(QComboBox, "cmbHeartbeatEvery")
    assert box is not None
    return box


def _choose(box: QComboBox, text: str) -> None:
    index = box.findText(text)
    assert index >= 0, text
    box.setCurrentIndex(index)
    box.activated.emit(index)  # what a click on the item does


def test_the_choices_are_the_offered_hours_and_the_default_is_marked_and_shown(
    page: AlertsPage,
) -> None:
    box = _combo(page)

    assert [box.itemData(i) for i in range(box.count())] == list(
        HEARTBEAT_HOURS_CHOICES
    )
    assert box.currentText() == "6 hours (default)"
    assert box.itemText(0) == "1 hour"


def test_a_choice_is_kept_at_once_and_reaches_the_heartbeat(page: AlertsPage) -> None:
    _choose(_combo(page), "12 hours")

    assert page.modes.heartbeat_hours() == 12
    assert page.modes.current().heartbeat_every == timedelta(hours=12)
    assert page.label(STATUS) == "Heartbeat interval saved."
    assert _combo(page).currentText() == "12 hours"


def test_choosing_the_default_again_puts_it_back_to_no_value(page: AlertsPage) -> None:
    _choose(_combo(page), "1 hour")

    _choose(_combo(page), "6 hours (default)")

    assert page.modes.heartbeat_hours() is None
    assert page.label(STATUS) == "The heartbeat is back to its default interval."


def test_what_was_chosen_before_is_shown_when_the_page_opens(
    qapp, request, monkeypatch, tmp_path
) -> None:
    modes = JsonAlertSettings(tmp_path / "state" / "alert_settings.json")
    modes.set_heartbeat_hours(24)

    page = build_page(request, monkeypatch, running=True, modes=modes)

    assert _combo(page).currentText() == "24 hours"


def test_a_read_only_copy_offers_no_change_and_says_why(
    qapp, request, monkeypatch, tmp_path
) -> None:
    modes = JsonAlertSettings(
        tmp_path / "state" / "alert_settings.json", read_only=True
    )

    page = build_page(request, monkeypatch, running=True, modes=modes)

    assert not _combo(page).isEnabled()
    assert "read-only" in page.label("lblHeartbeatNote")


def test_the_choice_is_off_while_the_work_is_out(page: AlertsPage) -> None:
    page.threads.held = []
    box = _combo(page)

    _choose(box, "2 hours")
    assert not box.isEnabled()

    page.threads.held[0]()
    assert _combo(page).isEnabled()


def test_an_unexpected_failure_shows_the_interval_that_was_kept_not_the_one_picked(
    qapp, request, monkeypatch, tmp_path
) -> None:
    class _Failing(JsonAlertSettings):
        def set_heartbeat_hours(self, hours: int | None) -> None:
            raise RuntimeError("secret detail the page must not show")

    modes = _Failing(tmp_path / "state" / "alert_settings.json")
    page = build_page(request, monkeypatch, running=True, modes=modes)

    _choose(_combo(page), "1 hour")

    assert _combo(page).currentText() == "6 hours (default)"
    assert "secret detail" not in page.told_the_user()
    assert "RuntimeError" in page.told_the_user()


def test_a_request_made_while_another_is_out_is_dropped_not_queued(
    page: AlertsPage,
) -> None:
    """The guard lives in the presenter's `_begin` (it was copied into each handler before): a
    second request while work is out starts nothing, whichever group it comes from."""
    page.threads.held = []
    view_model = page.presenter._settings_view_model

    view_model.heartbeat.request_hours(2)
    view_model.heartbeat.request_hours(3)
    view_model.channels.request_switch("discord", False)

    assert len(page.threads.held) == 1
    page.threads.held[0]()
    assert page.modes.heartbeat_hours() == 2
    assert page.modes.disabled() == frozenset()
