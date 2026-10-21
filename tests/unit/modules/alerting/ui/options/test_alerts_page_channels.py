"""`EPIC-036D8` — Tools → Options → Alerts: the "Channels" switches.

The page, `ChannelsSetup`, the catalog and the settings file (`JsonAlertSettings` under `tmp_path`)
are the real ones. A switch acts at once, like the page's buttons."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QCheckBox
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.options.alerts_page_world import (
    STATUS,
    AlertsPage,
    build_page,
)


@pytest.fixture
def page(qapp, request, monkeypatch) -> AlertsPage:
    return build_page(request, monkeypatch, running=True, telegram_running=True)


def _box(page: AlertsPage, channel: str) -> QCheckBox:
    box = page.view.findChild(QCheckBox, f"chkChannel_{channel}")
    assert box is not None, channel
    return box


def test_there_is_a_switch_per_running_channel_and_every_one_starts_on(
    page: AlertsPage,
) -> None:
    assert [_box(page, c).text() for c in ("discord", "telegram")] == [
        "Discord",
        "Telegram",
    ]
    assert _box(page, "discord").isChecked() and _box(page, "telegram").isChecked()
    assert page.label("lblChannelsNote") == ""


def test_clearing_a_switch_keeps_it_at_once_and_says_so(page: AlertsPage) -> None:
    _box(page, "telegram").click()

    assert page.modes.disabled() == {"telegram"}
    assert "switched off" in page.label(STATUS)
    assert not _box(page, "telegram").isChecked()
    assert _box(page, "discord").isChecked()


def test_ticking_it_again_switches_the_channel_back_on(page: AlertsPage) -> None:
    _box(page, "telegram").click()

    _box(page, "telegram").click()

    assert page.modes.disabled() == frozenset()
    assert page.label(STATUS) == "Channel switched on."


def test_what_was_switched_off_before_is_shown_when_the_page_opens(
    qapp, request, monkeypatch, tmp_path
) -> None:
    modes = JsonAlertSettings(tmp_path / "state" / "alert_settings.json")
    modes.disable("discord")

    page = build_page(
        request, monkeypatch, running=True, telegram_running=True, modes=modes
    )

    assert not _box(page, "discord").isChecked()
    assert _box(page, "telegram").isChecked()


def test_with_every_channel_off_the_page_says_nothing_is_sent_anywhere(
    page: AlertsPage,
) -> None:
    _box(page, "discord").click()
    _box(page, "telegram").click()

    assert "no alert is sent anywhere" in page.label("lblChannelsNote")


def test_with_no_channel_running_the_group_says_there_is_nothing_to_switch(
    qapp, request, monkeypatch
) -> None:
    page = build_page(request, monkeypatch)

    assert page.view.findChildren(QCheckBox, "chkChannel_discord") == []
    assert "No alert channel is running" in page.label("lblChannelsNote")


def test_a_read_only_copy_offers_no_switch_and_says_why(
    qapp, request, monkeypatch, tmp_path
) -> None:
    modes = JsonAlertSettings(
        tmp_path / "state" / "alert_settings.json", read_only=True
    )

    page = build_page(
        request, monkeypatch, running=True, telegram_running=True, modes=modes
    )

    assert not _box(page, "discord").isEnabled()
    assert "read-only" in page.label("lblChannelsNote")


def test_the_switches_are_off_while_the_work_is_out(page: AlertsPage) -> None:
    page.threads.held = []
    box = _box(page, "discord")

    box.click()
    assert not box.isEnabled()

    page.threads.held[0]()
    assert _box(page, "discord").isEnabled()


def test_an_unexpected_failure_shows_the_state_that_was_kept_not_the_one_clicked(
    qapp, request, monkeypatch, tmp_path
) -> None:
    class _Failing(JsonAlertSettings):
        def disable(self, channel_id: str) -> None:
            raise RuntimeError("secret detail the page must not show")

    modes = _Failing(tmp_path / "state" / "alert_settings.json")
    page = build_page(
        request, monkeypatch, running=True, telegram_running=True, modes=modes
    )

    _box(page, "discord").click()

    assert _box(page, "discord").isChecked()
    assert "secret detail" not in page.told_the_user()
    assert "RuntimeError" in page.told_the_user()
