"""`EPIC-036D7` — Tools → Options → Alerts: the "Who hears what" matrix.

The page, `RoutingSetup`, the catalog and the settings file (`JsonAlertSettings` under `tmp_path`)
are the real ones. A choice acts at once, like the page's buttons."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QComboBox, QLabel
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_route import AlertRoute
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import routing_words
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.options.alerts_page_world import (
    STATUS,
    AlertsPage,
    build_page,
)


@pytest.fixture
def page(qapp, request, monkeypatch) -> AlertsPage:
    return build_page(request, monkeypatch, running=True, telegram_running=True)


def _cell(page: AlertsPage, group: AlertGroup, channel: str) -> QComboBox:
    box = page.view.findChild(QComboBox, f"cmbRoute_{group.value}_{channel}")
    assert box is not None, (group, channel)
    return box


def _choose(box: QComboBox, text: str) -> None:
    index = box.findText(text)
    box.setCurrentIndex(index)
    box.activated.emit(index)  # what a click on the item does


def test_there_is_a_row_per_kind_of_alert_and_a_column_per_running_channel(
    page: AlertsPage,
) -> None:
    for group in AlertGroup:
        for channel in ("discord", "telegram"):
            box = _cell(page, group, channel)
            assert [box.itemText(i) for i in range(box.count())] == [
                "Default",
                "Loud",
                "Silent",
                "Off",
            ]
            assert box.currentText() == "Default"


def test_a_choice_is_kept_at_once_and_said(page: AlertsPage) -> None:
    _choose(_cell(page, AlertGroup.ROUTINE, "discord"), "Off")

    assert page.modes.routes() == (
        AlertRoute(AlertGroup.ROUTINE, "discord", Loudness.OFF),
    )
    assert page.label(STATUS) == "Routing saved."
    assert _cell(page, AlertGroup.ROUTINE, "discord").currentText() == "Off"


def test_choosing_default_puts_the_cell_back_to_no_route(page: AlertsPage) -> None:
    box = _cell(page, AlertGroup.NOTICES, "telegram")
    _choose(box, "Loud")

    _choose(box, "Default")

    assert page.modes.routes() == ()
    assert page.label(STATUS) == "That cell is back to its default."


def test_what_was_kept_before_is_shown_when_the_page_opens(
    qapp, request, monkeypatch, tmp_path
) -> None:
    modes = JsonAlertSettings(tmp_path / "state" / "alert_settings.json")
    modes.set_route(AlertGroup.INFRASTRUCTURE, "telegram", Loudness.SILENT)

    page = build_page(
        request, monkeypatch, running=True, telegram_running=True, modes=modes
    )

    assert _cell(page, AlertGroup.INFRASTRUCTURE, "telegram").currentText() == "Silent"
    assert _cell(page, AlertGroup.INFRASTRUCTURE, "discord").currentText() == "Default"


def test_the_page_says_a_critical_alert_still_reaches_two_channels(
    page: AlertsPage,
) -> None:
    text = page.view.findChild(QLabel, "lblRoutingCover").text()

    assert "Critical" in text and "two channels" in text


def test_with_no_channel_running_the_matrix_says_there_is_nothing_to_route(
    qapp, request, monkeypatch
) -> None:
    page = build_page(request, monkeypatch)

    assert page.view.findChildren(QComboBox, "cmbRoute_routine_discord") == []
    assert "nothing to route" in page.label("lblRoutingNote")


def test_a_read_only_copy_offers_no_change_and_says_why(
    qapp, request, monkeypatch, tmp_path
) -> None:
    modes = JsonAlertSettings(
        tmp_path / "state" / "alert_settings.json", read_only=True
    )

    page = build_page(
        request, monkeypatch, running=True, telegram_running=True, modes=modes
    )

    assert not _cell(page, AlertGroup.ROUTINE, "discord").isEnabled()
    assert "read-only" in page.label("lblRoutingNote")


def test_the_cells_are_off_while_the_work_is_out(page: AlertsPage) -> None:
    page.threads.held = []
    box = _cell(page, AlertGroup.ROUTINE, "discord")

    _choose(box, "Off")
    assert not box.isEnabled()

    page.threads.held[0]()
    assert _cell(page, AlertGroup.ROUTINE, "discord").isEnabled()


def test_the_matrix_has_exactly_the_groups_the_hub_routes_by() -> None:
    """A new `AlertGroup` is a new row, or this goes red (`EPIC-036D7` §3)."""
    assert [group for group, _name, _examples in routing_words.GROUP_ROWS] == list(
        AlertGroup
    )


def test_an_unexpected_failure_shows_the_value_that_was_kept_not_the_one_picked(
    qapp, request, monkeypatch, tmp_path
) -> None:
    """Review of PR #670: the combo must not keep saying what was never saved."""

    class _Failing(JsonAlertSettings):
        def set_route(self, group, channel_id, loudness) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("secret detail the page must not show")

    modes = _Failing(tmp_path / "state" / "alert_settings.json")
    page = build_page(
        request, monkeypatch, running=True, telegram_running=True, modes=modes
    )
    box = _cell(page, AlertGroup.ROUTINE, "discord")

    _choose(box, "Off")

    assert _cell(page, AlertGroup.ROUTINE, "discord").currentText() == "Default"
    assert "secret detail" not in page.told_the_user()
    assert "RuntimeError" in page.told_the_user()
