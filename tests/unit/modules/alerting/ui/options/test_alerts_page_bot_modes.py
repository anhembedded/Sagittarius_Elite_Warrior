"""`BOT-191` — Tools → Options → Alerts: the owner sets what each bot may tell, and it is kept.

The page over the real settings file (`JsonAlertSettings` under `tmp_path`) and the bots'
status report as the alert sources read it.
"""

from __future__ import annotations

import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QComboBox, QLabel
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode as Mode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import alerts_words
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    BOT,
    Bots,
    entry,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.options.alerts_page_world import (
    STATUS,
    AlertsPage,
    build_page,
)

OTHER = "zz9999"


def _two_bots() -> Bots:
    return Bots(entry(), replace(entry(), bot_id=OTHER, name="sol-grid"))


@pytest.fixture
def page(qapp, request, monkeypatch) -> AlertsPage:
    return build_page(request, monkeypatch, bots=_two_bots())


def _combo(page: AlertsPage, bot_id: str) -> QComboBox:
    box = page.view.findChild(QComboBox, f"cmbBotMode_{bot_id}")
    assert box is not None, f"no choice for {bot_id}"
    return box


def _choose(page: AlertsPage, bot_id: str, mode: Mode) -> None:
    box = _combo(page, bot_id)
    box.setCurrentIndex(box.findData(mode.value))
    box.activated.emit(box.currentIndex())


def test_every_bot_is_listed_with_all_messages_until_the_owner_says_otherwise(
    page,
) -> None:
    assert [
        (b.bot_id, b.name, b.mode) for b in page.presenter._settings_view_model.bot_rows
    ] == [(BOT, "eth-grid", "on"), (OTHER, "sol-grid", "on")]
    assert _combo(page, BOT).currentText() == alerts_words.BOT_MODE_LABELS[Mode.ON]
    assert [_combo(page, BOT).itemText(i) for i in range(3)] == [
        "All messages",
        "Critical only",
        "None",
    ]


def test_choosing_critical_only_is_kept_applied_to_the_next_alert_and_told(
    page,
) -> None:
    _choose(page, BOT, Mode.CRITICAL_ONLY)

    assert page.modes.current().mode_of(BOT) is Mode.CRITICAL_ONLY
    assert page.modes.current().mode_of(OTHER) is Mode.ON
    assert page.label(STATUS) == alerts_words.MODE_SAVED[Mode.CRITICAL_ONLY]
    assert _combo(page, BOT).currentData() == "critical_only"


def test_the_choice_is_there_after_a_restart(page, request, monkeypatch) -> None:
    _choose(page, BOT, Mode.OFF)
    path = request.getfixturevalue("tmp_path") / "state" / "alert_settings.json"

    reopened = build_page(
        request,
        monkeypatch,
        bots=_two_bots(),
        modes=JsonAlertSettings(path),
    )

    assert _combo(reopened, BOT).currentData() == "off"
    assert _combo(reopened, OTHER).currentData() == "on"


def test_setting_a_bot_back_to_all_messages_is_kept(page) -> None:
    _choose(page, BOT, Mode.OFF)
    _choose(page, BOT, Mode.ON)

    assert page.modes.current().mode_of(BOT) is Mode.ON
    assert page.label(STATUS) == alerts_words.MODE_SAVED[Mode.ON]


def test_a_choice_that_cannot_be_kept_shows_what_is_really_set_and_says_so(
    page, monkeypatch
) -> None:
    def refuse(_bot_id: str, _mode: Mode) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(page.modes, "set_mode", refuse)

    _choose(page, BOT, Mode.OFF)

    assert _combo(page, BOT).currentData() == "on"
    assert "failed unexpectedly" in page.told_the_user()
    assert "disk full" not in page.told_the_user()


def test_no_bots_is_said_in_words(qapp, request, monkeypatch) -> None:
    empty = build_page(request, monkeypatch, bots=Bots())

    assert [
        box
        for box in empty.view.findChildren(QComboBox)
        if box.objectName().startswith("cmbBotMode_")
    ] == []
    assert empty.label("lblAlertsBotsNote") == alerts_words.NO_BOTS
    assert (
        empty.view.findChild(QLabel, "lblAlertsBotsIntro").text()
        == alerts_words.BOTS_INTRO
    )


def test_a_choice_the_page_does_not_know_is_ignored(page) -> None:
    page.presenter._settings_view_model.request_bot_mode(BOT, "shout")

    assert page.modes.current().mode_of(BOT) is Mode.ON


def test_a_read_only_copy_offers_no_choice_and_says_why(
    qapp, request, monkeypatch
) -> None:
    """Its alerting never runs: a choice made here would reach nothing and only look saved."""
    path = request.getfixturevalue("tmp_path") / "state" / "alert_settings.json"
    read_only = build_page(
        request,
        monkeypatch,
        bots=_two_bots(),
        modes=JsonAlertSettings(path, read_only=True),
    )

    assert not _combo(read_only, BOT).isEnabled()
    assert read_only.label("lblAlertsBotsNote") == alerts_words.READ_ONLY_NOTE
    # Asked anyway, as a stray signal would: nothing is changed or told as saved.
    read_only.presenter._settings_view_model.request_bot_mode(BOT, "off")
    assert read_only.modes.current().mode_of(BOT) is Mode.ON
    assert read_only.label(STATUS) == ""


def test_choosing_keeps_the_combo_the_owner_used(page) -> None:
    """The rows are not rebuilt when the bots are the same, so the focus stays where it was."""
    before = _combo(page, BOT)

    _choose(page, BOT, Mode.CRITICAL_ONLY)

    assert _combo(page, BOT) is before


def test_a_bot_list_that_cannot_be_read_is_said_in_words_and_opens_no_box(
    qapp, request, monkeypatch
) -> None:
    class _Broken(Bots):
        def dispatch(self, handler_class, input_dto=None):
            raise RuntimeError("store unreadable")

    broken = build_page(request, monkeypatch, bots=_Broken())

    assert broken.label("lblAlertsBotsNote") == alerts_words.BOTS_UNREADABLE
    assert broken.notifier.failures == []
