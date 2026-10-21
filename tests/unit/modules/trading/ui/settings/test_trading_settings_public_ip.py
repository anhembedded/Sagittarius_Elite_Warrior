"""`BOT-224` — Show public IP on the Trading page of Tools → Options.

@details Over the real presenter, view and view model (`key_page_world`), with only the
IP-echo service scripted: the address is asked for on the click and never otherwise,
it is shown as selectable text with a Copy button and the line on what to do with it,
a failure is one sentence, the `-2015` row names the address once it is known, and a
lookup still out when the dialog closes is dropped.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QListWidget, QPushButton
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.public_address_lookup import (
    PublicAddressFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.settings.public_address_words import (
    ADVICE,
    failure_words,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.settings.key_page_world import (
    KEY,
    PUBLIC_IP,
    KeyPage,
    build_page,
    mainnet_accepts,
    status_of,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.options_dialog import (
    OptionsDialog,
)

_FUTURES_MAINNET = TradingVenue.FUTURES_MAINNET


@pytest.fixture
def page(qapp, tmp_path, request) -> KeyPage:
    return build_page(tmp_path, request)


def _widget(page: KeyPage, cls, name: str):
    return page.view.findChild(cls, name)


def _visible(page: KeyPage, cls, name: str) -> bool:
    return not _widget(page, cls, name).isHidden()


def _mainnet_key_refused_by_the_allowlist(page: KeyPage) -> None:
    page.probe.verdicts = mainnet_accepts(futures=True)
    page.type_in_dialog(KEY)
    page.click_add()
    page.statuses.by_venue[_FUTURES_MAINNET] = status_of(
        _FUTURES_MAINNET, ConnectionFailureKind.KEY_REJECTED
    )
    page.click_check()


def test_the_address_is_asked_for_only_when_the_button_is_pressed(page) -> None:
    _mainnet_key_refused_by_the_allowlist(page)
    page.presenter.revert()

    assert page.addresses.asked == 0

    _widget(page, QPushButton, "btnShowPublicIp").click()

    assert page.addresses.asked == 1


def test_nothing_about_the_address_shows_before_it_is_looked_up(page) -> None:
    assert not _visible(page, QLabel, "lblPublicIp")
    assert not _visible(page, QPushButton, "btnCopyPublicIp")
    assert not _visible(page, QLabel, "lblPublicIpAdvice")
    assert not _visible(page, QLabel, "lblPublicIpProblem")


def test_the_address_is_selectable_text_with_a_copy_button_and_the_whitelist_advice(
    page,
) -> None:
    _widget(page, QPushButton, "btnShowPublicIp").click()

    value = _widget(page, QLabel, "lblPublicIp")
    assert value.text() == PUBLIC_IP
    assert value.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
    assert _visible(page, QPushButton, "btnCopyPublicIp")
    advice = _widget(page, QLabel, "lblPublicIpAdvice")
    assert advice.text() == ADVICE
    assert "whitelist" in ADVICE and "192.168" in ADVICE


def test_copy_puts_the_address_and_only_the_address_on_the_clipboard(page) -> None:
    _widget(page, QPushButton, "btnShowPublicIp").click()

    _widget(page, QPushButton, "btnCopyPublicIp").click()

    assert QGuiApplication.clipboard().text() == PUBLIC_IP


@pytest.mark.parametrize("failure", list(PublicAddressFailure))
def test_a_failed_lookup_is_one_plain_sentence_and_no_message_box(
    page, failure
) -> None:
    page.addresses.fail(failure)

    _widget(page, QPushButton, "btnShowPublicIp").click()

    problem = _widget(page, QLabel, "lblPublicIpProblem")
    assert problem.text() == f"Error: {failure_words(failure)}"
    assert page.notifier.failures == []
    assert not _visible(page, QPushButton, "btnCopyPublicIp")
    assert not _visible(page, QLabel, "lblPublicIpAdvice")


def test_a_failure_after_a_success_does_not_leave_the_old_address_on_show(page) -> None:
    _widget(page, QPushButton, "btnShowPublicIp").click()
    page.addresses.fail(PublicAddressFailure.UNREACHABLE)

    _widget(page, QPushButton, "btnShowPublicIp").click()

    assert not _visible(page, QLabel, "lblPublicIp")
    assert _visible(page, QLabel, "lblPublicIpProblem")


def test_a_refused_key_says_which_address_to_whitelist_once_it_is_known(page) -> None:
    _mainnet_key_refused_by_the_allowlist(page)
    before = page.row(_FUTURES_MAINNET).state
    assert PUBLIC_IP not in before

    _widget(page, QPushButton, "btnShowPublicIp").click()

    after = page.row(_FUTURES_MAINNET).state
    assert PUBLIC_IP in after
    assert "allowlist" in after and "192.168" in after


def test_a_failed_lookup_leaves_the_refused_keys_words_as_they_were(page) -> None:
    _mainnet_key_refused_by_the_allowlist(page)
    before = page.row(_FUTURES_MAINNET).state
    page.addresses.fail(PublicAddressFailure.UNREACHABLE)

    _widget(page, QPushButton, "btnShowPublicIp").click()

    assert page.row(_FUTURES_MAINNET).state == before


def test_the_address_is_not_logged_at_info_or_above(page, caplog) -> None:
    with caplog.at_level("INFO"):
        _widget(page, QPushButton, "btnShowPublicIp").click()
        page.click_check()

    assert PUBLIC_IP not in caplog.text


def test_the_buttons_are_off_while_the_lookup_runs(page) -> None:
    page.threads.held = []

    _widget(page, QPushButton, "btnShowPublicIp").click()

    assert not _widget(page, QPushButton, "btnShowPublicIp").isEnabled()
    assert not _widget(page, QPushButton, "btnCheckConnections").isEnabled()
    for release in page.threads.held:
        release()
    assert _widget(page, QPushButton, "btnShowPublicIp").isEnabled()


def test_a_lookup_still_out_when_the_dialog_closes_is_dropped(page) -> None:
    page.threads.held = []
    _widget(page, QPushButton, "btnShowPublicIp").click()

    page.view.dialogClosed.emit()
    for release in page.threads.held:
        release()

    assert page.presenter._settings_view_model.busy is False
    assert page.presenter._settings_view_model.publicIp == ""
    assert page.presenter._public_address == ""


def test_closing_the_dialog_does_not_drop_a_key_check_that_is_running(page) -> None:
    page.threads.held = []
    page.click_check()

    page.view.dialogClosed.emit()

    assert page.presenter._settings_view_model.busy is True


@pytest.mark.parametrize("way_out", ["accept", "reject"])
def test_the_real_options_dialog_closing_drops_a_lookup_still_out(
    qapp, page, way_out
) -> None:
    dialog = OptionsDialog([page.presenter])
    dialog.show()
    page.threads.held = []
    _widget(page, QPushButton, "btnShowPublicIp").click()

    getattr(dialog, way_out)()
    for release in page.threads.held:
        release()

    assert page.presenter._settings_view_model.busy is False
    assert page.presenter._settings_view_model.publicIp == ""
    dialog.deleteLater()


def test_choosing_another_options_page_does_not_drop_the_lookup(qapp, page) -> None:
    other = QLabel("another page")
    dialog = OptionsDialog([page.presenter, _PageOf(other)])
    dialog.show()
    page.threads.held = []
    _widget(page, QPushButton, "btnShowPublicIp").click()

    dialog.findChild(QListWidget, "workbench::options::sections").setCurrentRow(1)
    for release in page.threads.held:
        release()

    assert page.presenter._settings_view_model.publicIp == PUBLIC_IP
    dialog.reject()
    dialog.deleteLater()


class _PageOf:
    """A second Options page, only so the dialog has another to switch to."""

    title = "Other"

    def __init__(self, widget: QLabel) -> None:
        self._widget = widget

    def widget(self) -> QLabel:
        return self._widget

    def apply(self) -> None:
        return None

    def revert(self) -> None:
        return None

    def is_dirty(self) -> bool:
        return False

    def validation_message(self) -> None:
        return None

    def set_change_listener(self, listener) -> None:
        return None
