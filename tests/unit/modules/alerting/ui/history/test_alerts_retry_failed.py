"""`EPIC-036D5` — the Retry failed button on the Alerts screen, over the real outbox, history
and presenter; only the channel is scripted. The pool runs inline, or holds the work."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QPushButton
from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.retry_failed_deliveries import (
    RetryFailedDeliveries,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.history import history_words
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.history.alerts_world import (
    AlertsScreen,
    WritableCopy,
    build_screen,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import an_alert


@pytest.fixture
def screen(qapp, request, tmp_path: Path) -> AlertsScreen:
    return build_screen(request, tmp_path)


def _retry(screen: AlertsScreen) -> QPushButton:
    button = screen.view.findChild(QPushButton, "btnRetryFailed")
    assert button is not None
    return button


def _fail_one(screen: AlertsScreen) -> None:
    screen.rig.channels["discord"].script.append(
        DeliveryResult.refused("webhook deleted")
    )
    screen.rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    screen.rig.deliver_all()


def _halted_delivery(screen: AlertsScreen) -> str:
    """The delivery cell of the halted bot's alert; a failing channel raises an alert of its
    own, which sits above it."""
    [text] = [
        screen.cell(row, "delivery")
        for row in range(screen.view.shown_count)
        if screen.cell(row, "alert") == an_alert(AlertKind.BOT_HALTED).title
    ]
    return text


def test_retry_failed_sends_a_failed_delivery_again_and_says_so(
    screen: AlertsScreen,
) -> None:
    _fail_one(screen)
    screen.refresh()
    assert _halted_delivery(screen).startswith("Discord: failed")

    _retry(screen).click()
    screen.rig.deliver_all()
    screen.refresh()

    assert _halted_delivery(screen).startswith("Discord: delivered")


def test_the_answer_stays_on_screen_over_the_read_that_follows(
    screen: AlertsScreen,
) -> None:
    _fail_one(screen)

    _retry(screen).click()

    assert screen.view.history_note == history_words.retry_done(1)
    assert _retry(screen).isEnabled()


def test_with_nothing_failed_it_says_nothing_to_retry(screen: AlertsScreen) -> None:
    _retry(screen).click()

    assert screen.view.history_note == history_words.RETRY_NONE


def test_the_button_is_off_while_the_work_is_out_and_a_second_click_does_nothing(
    screen: AlertsScreen,
) -> None:
    _fail_one(screen)
    screen.threads.held = []

    _retry(screen).click()
    assert not _retry(screen).isEnabled()
    assert screen.view.history_note == history_words.RETRYING
    screen.presenter.retry_failed()
    assert len(screen.threads.held) == 1

    screen.threads.held[0]()
    assert _retry(screen).isEnabled()


def test_a_copy_that_may_not_write_cannot_retry(qapp, request, tmp_path: Path) -> None:
    screen = build_screen(
        request, tmp_path, services={IInstanceAccess: WritableCopy(read_only=True)}
    )

    assert not _retry(screen).isEnabled()
    assert _retry(screen).toolTip() == history_words.RETRY_READ_ONLY


def test_a_failed_retry_is_told_by_type_and_leaves_the_screen_usable(
    qapp, request, tmp_path: Path
) -> None:
    class _Broken(RetryFailedDeliveries):
        def run(self) -> int:
            raise RuntimeError("secret detail the screen must not show")

    screen = build_screen(request, tmp_path)
    screen.presenter._retry = _Broken(None, screen.rig.clock, None)  # type: ignore[arg-type]

    _retry(screen).click()

    note = screen.view.history_note
    assert "RuntimeError" in note
    assert "secret detail" not in note
    assert _retry(screen).isEnabled()
