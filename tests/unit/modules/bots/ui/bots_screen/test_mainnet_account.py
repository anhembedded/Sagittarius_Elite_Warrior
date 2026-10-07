"""`EPIC-034E` — Bots → Mainnet account: the owner's real account, read only.

The text is pure and tested on its own; the command and the window are tested
on the screen's real wiring, with the mainnet source answered by the verified
fake (`FakeVenueAccountReader`) behind the real `GetMainnetAccountQuery`.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtWidgets import QPlainTextEdit
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_commands import (
    MAINNET_ACCOUNT,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.mainnet_account_dialog import (
    MainnetAccountDialog,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.mainnet_account_text import (
    ADVICE_READ_ONLY_KEY,
    UNKNOWN_BEYOND_READING,
    account_text,
    error_text,
    failure_text,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.key_permissions import (
    KeyPermissions,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.testing.fake_venue_account_snapshot import (
    a_venue_account_snapshot,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.account_source import (
    AccountSource,
)

from .bots_screen_fixtures import BotsScreen

_MAINNET = AccountSource.SPOT_MAINNET_READONLY
_READ_ONLY = KeyPermissions(
    can_read=True,
    can_trade_spot=False,
    can_withdraw=False,
    can_trade_margin=False,
    can_trade_futures=False,
    can_transfer=False,
)


def _snapshot(permissions: KeyPermissions | None = _READ_ONLY, orders: int | None = 3):
    return replace(
        a_venue_account_snapshot(_MAINNET),
        key_permissions=permissions,
        open_order_count=orders,
    )


def test_a_connected_account_says_its_title_key_balances_fees_and_orders() -> None:
    text = account_text(_snapshot())

    assert text.headline == "Mainnet · read only: Connected"
    body = "\n".join(text.lines)
    assert "Key: can read, cannot trade Spot, cannot withdraw" in body
    assert "Available to spend: 900.00 USDT" in body
    assert "Fees: maker 0.10%, taker 0.10%" in body
    assert "Open orders: 3" in body
    assert "BTC: 0.5 free, 0 in orders" in body
    assert "can do more than read" not in body
    assert UNKNOWN_BEYOND_READING not in body
    assert "spot_mainnet_readonly" not in text.headline + body


def test_a_key_that_can_trade_is_accepted_with_the_advice_to_make_a_read_only_one() -> (
    None
):
    trading = replace(_READ_ONLY, can_trade_spot=True)

    body = "\n".join(account_text(_snapshot(trading)).lines)

    assert "Key: can read, can trade Spot, cannot withdraw" in body
    assert ADVICE_READ_ONLY_KEY.format("trade Spot") in body


@pytest.mark.parametrize(
    ("grant", "words"),
    [
        ({"can_trade_margin": True}, "trade Margin"),
        ({"can_trade_futures": True}, "trade Futures"),
        ({"can_transfer": True}, "transfer between accounts"),
    ],
)
def test_a_key_with_any_other_power_is_not_called_read_only(grant, words) -> None:
    permissions = replace(_READ_ONLY, **grant)

    body = "\n".join(account_text(_snapshot(permissions)).lines)

    assert not permissions.is_read_only
    assert ADVICE_READ_ONLY_KEY.format(words) in body


def test_a_key_whose_other_powers_the_exchange_did_not_say_is_not_called_read_only() -> (
    None
):
    unknown = KeyPermissions(can_read=True, can_trade_spot=False, can_withdraw=False)

    body = "\n".join(account_text(_snapshot(unknown)).lines)

    assert not unknown.is_read_only
    assert UNKNOWN_BEYOND_READING in body


def test_what_the_exchange_did_not_say_is_said_not_to_have_been_read() -> None:
    body = "\n".join(account_text(_snapshot(permissions=None, orders=None)).lines)

    assert "Key permissions: not read" in body
    assert "Open orders: not read" in body


def test_a_key_that_can_withdraw_is_refused_naming_the_permission() -> None:
    refusal = ConnectFailure(
        _MAINNET, ConnectionFailureKind.WITHDRAWAL_ENABLED, "withdrawals"
    )

    text = failure_text(refusal)

    assert text.headline == "Mainnet · read only: not connected"
    assert "can withdraw funds" in text.lines[0]
    assert "read-only key" in text.lines[0]


def test_no_key_says_where_to_set_one() -> None:
    text = failure_text(ConnectFailure(_MAINNET, ConnectionFailureKind.NOT_CONFIGURED))

    assert "API key" in text.lines[0]


def test_a_read_that_raised_is_said() -> None:
    assert "boom" in error_text("boom").lines[0]


def test_the_command_is_always_available_and_asks_the_screen_to_show_it(
    open_bots_screen,
) -> None:
    screen = open_bots_screen()

    action = screen.actions.action(MAINNET_ACCOUNT)

    assert action.isEnabled()
    action.trigger()
    assert "mainnet account" in screen.answers.asked


def _open(screen: BotsScreen, qtbot) -> MainnetAccountDialog:
    dialog = MainnetAccountDialog(screen.view, screen.pool, screen.dispatcher)
    qtbot.addWidget(dialog)
    return dialog


def test_the_window_says_it_is_reading_then_shows_the_account(
    open_bots_screen, qtbot
) -> None:
    screen = open_bots_screen()
    screen.mainnet.answer_with(_snapshot())
    dialog = _open(screen, qtbot)

    dialog.read()
    assert dialog.headline.text() == "Mainnet · read only: Reading the account…"
    screen.settle()

    assert dialog.headline.text() == "Mainnet · read only: Connected"
    assert "Open orders: 3" in dialog.body.toPlainText()
    assert screen.mainnet.symbols_read == ["BTCUSDT"]


def test_the_window_shows_why_a_key_was_refused(open_bots_screen, qtbot) -> None:
    screen = open_bots_screen()
    screen.mainnet.answer_with(
        ConnectFailure(
            _MAINNET, ConnectionFailureKind.WITHDRAWAL_ENABLED, "withdrawals"
        )
    )
    dialog = _open(screen, qtbot)

    dialog.read()
    screen.settle()

    assert dialog.headline.text() == "Mainnet · read only: not connected"
    assert "can withdraw funds" in dialog.body.toPlainText()


def test_closing_the_window_drops_an_answer_still_on_its_way(
    open_bots_screen, qtbot
) -> None:
    screen = open_bots_screen()
    screen.mainnet.answer_with(_snapshot())
    dialog = _open(screen, qtbot)
    dialog.read()

    dialog.reject()
    screen.settle()

    assert dialog.headline.text() == "Mainnet · read only: Reading the account…"


def test_the_window_has_a_read_only_text_and_only_a_close_button(
    open_bots_screen, qtbot
) -> None:
    from PySide6.QtWidgets import QAbstractButton

    dialog = _open(open_bots_screen(), qtbot)

    assert dialog.findChild(QPlainTextEdit).isReadOnly()
    assert [
        b.text().replace("&", "") for b in dialog.findChildren(QAbstractButton)
    ] == ["Close"]
