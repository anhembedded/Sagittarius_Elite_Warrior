"""`EPIC-036D4` — Tools → Options → Alerts: the Telegram bot token and chat id.

The page, `TelegramCredentialsSetup`, the catalog and the Telegram channel are the real ones;
the secret store is in memory and the transport is scripted (`alerts_page_world`). The token is
a secret: it must never be on the screen once saved, in a log or in a notice.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlsplit

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QLineEdit
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.telegram_channel import (
    TELEGRAM_CHAT_SECRET,
    TELEGRAM_TOKEN_SECRET,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.options.alerts_page_world import (
    SEND_TEST,
    STATUS,
    AlertsPage,
    assert_no_secret,
    build_page,
)

BOT_KEY = "123456789:AAH-top_secret_TOKEN_abcdefghijklmnopqrst"
CHAT = "5550123"
TG_SAVE = "btnSaveTelegram"
TG_REMOVE = "btnRemoveTelegram"
TG_CHANNEL = "lblTelegramChannelState"
TG_SAVED = "lblTelegramSaved"
#: Every part of the token that is secret (the four characters the page shows are not).
KEY_PARTS = ("top_secret", "AAH-top", "123456789:AAH")


def _fill(page: AlertsPage, token: str, chat: str) -> None:
    page.view.findChild(QLineEdit, "txtTelegramToken").setText(token)
    page.view.findChild(QLineEdit, "txtTelegramChat").setText(chat)


def _stored_page(request, monkeypatch, *, running: bool) -> AlertsPage:  # type: ignore[no-untyped-def]
    return build_page(
        request,
        monkeypatch,
        store=InMemorySecretStore(
            **{TELEGRAM_TOKEN_SECRET: BOT_KEY, TELEGRAM_CHAT_SECRET: CHAT}
        ),
        telegram_running=running,
    )


@pytest.fixture
def page(qapp, request, monkeypatch) -> AlertsPage:
    return build_page(request, monkeypatch)


def test_the_token_field_is_masked_and_the_chat_field_is_not(page) -> None:
    token = page.view.findChild(QLineEdit, "txtTelegramToken")
    chat = page.view.findChild(QLineEdit, "txtTelegramChat")

    assert token.echoMode() is QLineEdit.EchoMode.Password
    assert chat.echoMode() is QLineEdit.EchoMode.Normal


def test_with_nothing_saved_the_page_says_telegram_is_off(page) -> None:
    assert page.label(TG_CHANNEL) == "Off: no Telegram bot is saved."
    assert page.label(TG_SAVED) == "No bot saved."
    assert not page.button(TG_REMOVE).isEnabled()


def test_save_stores_the_pair_clears_the_fields_and_says_what_to_do_next(page) -> None:
    _fill(page, BOT_KEY, CHAT)

    page.click(TG_SAVE)

    assert page.store.read(TELEGRAM_TOKEN_SECRET) == BOT_KEY
    assert page.store.read(TELEGRAM_CHAT_SECRET) == CHAT
    assert page.view.findChild(QLineEdit, "txtTelegramToken").text() == ""
    assert page.label(STATUS) == "Telegram bot saved."
    assert page.label(TG_CHANNEL) == (
        "Saved, not sending yet: restart the app to start sending."
    )
    assert (
        page.label(TG_SAVED) == f"Saved bot token ending …{BOT_KEY[-4:]}, chat {CHAT}"
    )
    assert page.button(TG_REMOVE).isEnabled()
    assert_no_secret_in(page.everything_on_screen(), "the page after a save")


@pytest.mark.parametrize(
    ("token", "chat", "fragment"),
    [
        ("", CHAT, "paste the bot token"),
        (BOT_KEY, "", "enter the chat id"),
        ("hello", CHAT, "not a telegram bot token"),
        (BOT_KEY, "not a chat", "not a chat id"),
    ],
    ids=["no-token", "no-chat", "bad-token", "bad-chat"],
)
def test_an_invalid_value_is_not_saved_and_the_page_says_why(
    page, token: str, chat: str, fragment: str
) -> None:
    _fill(page, token, chat)

    page.click(TG_SAVE)

    assert fragment in page.label(STATUS).lower()
    assert page.store.secrets == {}


def test_saving_again_over_a_saved_pair_replaces_it(request, monkeypatch, qapp) -> None:
    page = _stored_page(request, monkeypatch, running=True)
    new_key = "987654321:AAH-another_secret_TOKEN_zyxwvutsrqponm"
    _fill(page, new_key, "77")

    page.click(TG_SAVE)

    assert page.store.read(TELEGRAM_TOKEN_SECRET) == new_key
    assert page.label(TG_SAVED).endswith(f"{new_key[-4:]}, chat 77")
    assert page.label(TG_CHANNEL) == "On: alerts go to the saved Telegram bot."


def test_remove_asks_with_its_own_verbs_and_keeping_is_the_default(
    request, monkeypatch, qapp
) -> None:
    page = _stored_page(request, monkeypatch, running=True)
    page.answers.append(False)

    page.click(TG_REMOVE)

    [question] = page.asked
    assert (question.act, question.keep) == ("Remove bot", "Keep bot")
    assert page.store.read(TELEGRAM_TOKEN_SECRET) == BOT_KEY, "keeping must keep"


def test_confirmed_remove_forgets_the_pair_and_says_when_it_stops(
    request, monkeypatch, qapp
) -> None:
    page = _stored_page(request, monkeypatch, running=True)
    page.answers.append(True)

    page.click(TG_REMOVE)

    assert page.store.secrets == {}
    assert page.label(STATUS) == "Telegram bot removed."
    assert "restart the app" in page.label(TG_CHANNEL)


def test_send_test_works_with_only_telegram_saved_and_posts_to_it(
    request, monkeypatch, qapp
) -> None:
    page = _stored_page(request, monkeypatch, running=False)

    page.click(SEND_TEST)

    [post] = page.transport.posts
    assert urlsplit(post.url).hostname == "api.telegram.org"
    assert page.label(STATUS) == "Test message sent to Telegram. Check the channel."


def test_send_test_is_off_when_neither_channel_is_saved(page) -> None:
    assert not page.button(SEND_TEST).isEnabled()


def test_a_refused_telegram_test_tells_what_to_check_not_the_token(
    request, monkeypatch, qapp
) -> None:
    from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
        WebhookResponse,
    )
    from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.ui.options.alerts_page_world import (
        FakeWebhookTransport,
    )

    transport = FakeWebhookTransport(
        [WebhookResponse(401, {}, b'{"ok": false, "description": "Unauthorized"}')]
    )
    page = build_page(
        request,
        monkeypatch,
        store=InMemorySecretStore(
            **{TELEGRAM_TOKEN_SECRET: BOT_KEY, TELEGRAM_CHAT_SECRET: CHAT}
        ),
        telegram_running=False,
        transport=transport,
    )

    page.click(SEND_TEST)

    text = page.label(STATUS)
    assert "Test message not sent" in text
    assert "bot token and chat id" in text
    assert_no_secret_in(text, "the status after a refused test")


def test_no_log_record_notice_or_label_holds_the_token(
    request, monkeypatch, qapp, caplog: pytest.LogCaptureFixture
) -> None:
    page = build_page(request, monkeypatch)
    with caplog.at_level(logging.DEBUG):
        _fill(page, BOT_KEY, CHAT)
        page.click(TG_SAVE)
        page.click(SEND_TEST)
        page.answers.append(True)
        page.click(TG_REMOVE)

    assert_no_secret_in(caplog.text, "the log")
    assert_no_secret_in(page.told_the_user(), "a notice")
    assert_no_secret_in(page.everything_on_screen(), "the page")


def assert_no_secret_in(text: str, where: str) -> None:
    for part in KEY_PARTS:
        assert part not in text, f"{part!r} leaked into {where}"
    # The page may show the four characters it was designed to show, and nothing around them.
    assert_no_secret(text, where)


def test_a_mixed_send_test_says_which_channel_got_it_and_which_did_not() -> None:
    from Sagittarius_Elite_Warrior.src.modules.alerting.application.send_test_message import (
        ChannelTestOutcome,
    )
    from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
        DeliveryResult,
    )
    from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import alerts_words

    sentence, is_error = alerts_words.send_test_words(
        (
            ChannelTestOutcome("telegram", DeliveryResult.sent()),
            ChannelTestOutcome("discord", DeliveryResult.refused("refused (404)")),
        )
    )

    assert is_error
    assert sentence.startswith(
        "Sent to Telegram. Test message not sent: refused (404)."
    )
