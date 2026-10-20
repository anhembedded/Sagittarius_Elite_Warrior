"""`EPIC-036C1` - the body of a Telegram `sendMessage` for an alert."""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.telegram_message import (
    MAX_TEXT,
    telegram_payload,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness

_AT = datetime(2026, 10, 16, 2, 30, tzinfo=UTC)


def _halt(detail: str = "price feed silent for 64 s", name: str = "eth-grid") -> Alert:
    return Alert.raised(
        AlertKind.BOT_HALTED,
        AlertSubject.bot("g3n092", name, "grid", "spot_mainnet", "ETHUSDT"),
        f"Bot halted: {name}",
        detail,
        _AT,
    )


def test_a_halt_names_the_severity_the_bot_the_reason_and_the_chat() -> None:
    body = telegram_payload("42", _halt(), Loudness.LOUD)

    text = str(body["text"])
    assert body["chat_id"] == "42"
    assert "CRITICAL" in text
    assert "Bot halted: eth-grid" in text
    assert "spot_mainnet ETHUSDT" in text
    assert "price feed silent for 64 s" in text
    assert "2026-10-16 02:30:00 UTC" in text


def test_a_silent_cell_sets_disable_notification_and_a_loud_one_does_not() -> None:
    assert (
        telegram_payload("42", _halt(), Loudness.SILENT)["disable_notification"] is True
    )
    assert (
        telegram_payload("42", _halt(), Loudness.LOUD)["disable_notification"] is False
    )


def test_text_from_an_alert_cannot_become_markup() -> None:
    """A bot name or an exchange message is text somebody typed or sent: `<b>` and `&` in it
    must reach the chat as characters, in a message sent with `parse_mode` HTML."""
    body = telegram_payload(
        "42",
        _halt(detail="a <b>bold</b> & <a href='x'>link</a>", name="<i>x</i>"),
        Loudness.LOUD,
    )

    text = str(body["text"])
    assert body["parse_mode"] == "HTML"
    assert "&lt;b&gt;bold&lt;/b&gt; &amp; &lt;a href=" in text
    assert "<i>x</i>" not in text
    # the only tags are the ones the message itself writes: one bold head
    assert text.count("<") == text.count("</b>") * 2 == 2


def test_a_long_detail_is_cut_to_what_telegram_accepts_even_when_escaping_grows_it() -> (
    None
):
    body = telegram_payload("42", _halt(detail="&" * 10_000), Loudness.LOUD)

    text = str(body["text"])
    assert len(text) <= MAX_TEXT
    assert text.endswith("UTC") or "\N{HORIZONTAL ELLIPSIS}" in text
    assert "&amp;" in text


def test_a_cut_never_leaves_half_an_entity() -> None:
    body = telegram_payload("42", _halt(detail="<" * 10_000), Loudness.LOUD)

    text = str(body["text"])
    assert len(text) <= MAX_TEXT
    assert "&l" not in text.replace("&lt;", "")
