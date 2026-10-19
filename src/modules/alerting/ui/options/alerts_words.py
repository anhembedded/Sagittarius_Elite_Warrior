"""What the Alerts page tells the owner (`EPIC-036D1`): every sentence in one file.

Each sentence says what happened, why, and what to do (MS `mess-error`), and none
carries the webhook: a message is chosen by the outcome of the use case, never built
from the typed value. `DeliveryResult.reason` is the one text from outside, and its
contract is that it never carries a URL, a token or a response body.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.application.discord_webhook_setup import (
    DiscordChannelState,
    WebhookRemoval,
    WebhookSave,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.send_test_message import (
    ChannelTestOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

WHERE_TO_COPY_IT = (
    "In Discord: Channel settings → Integrations → Webhooks → Copy Webhook URL."
)

SAVE_WORDS: dict[WebhookSave, tuple[str, bool]] = {
    WebhookSave.SAVED: ("Webhook saved.", False),
    WebhookSave.EMPTY: ("Paste the webhook URL first.", True),
    WebhookSave.NOT_A_DISCORD_WEBHOOK: (
        (
            "That is not a Discord webhook URL, so nothing was saved. A webhook URL "
            f"starts with https://discord.com/api/webhooks/. {WHERE_TO_COPY_IT}"
        ),
        True,
    ),
    WebhookSave.STORE_UNAVAILABLE: (
        (
            "The operating system's keyring cannot store a secret here, so nothing "
            "was saved. Unlock or enable the keyring, then save again."
        ),
        True,
    ),
    WebhookSave.OVERRIDDEN: (
        (
            "Saved to the keyring, but this machine reads the webhook from a systemd "
            "credential or secret file first, so the saved one is not used. Change it "
            "where that is provisioned."
        ),
        True,
    ),
}

REMOVAL_WORDS: dict[WebhookRemoval, tuple[str, bool]] = {
    WebhookRemoval.REMOVED: ("Webhook removed.", False),
    WebhookRemoval.NOTHING_STORED: ("No webhook was saved.", False),
    WebhookRemoval.STORE_UNAVAILABLE: (
        (
            "The operating system's keyring cannot remove a secret here, so the "
            "webhook is still saved. Unlock or enable the keyring, then remove it again."
        ),
        True,
    ),
    WebhookRemoval.STILL_SET_ELSEWHERE: (
        (
            "The keyring entry is removed, but the webhook is still set by a systemd "
            "credential or secret file, so the channel stays configured. Remove it "
            "where that is provisioned."
        ),
        True,
    ),
}

NOTHING_TO_TEST = (
    "No Discord webhook is saved, so there is nothing to test. Save one first."
)
TEST_SENT = "Test message sent to Discord. Check the channel."
UNEXPECTED_HEADLINE = (
    "{doing} failed unexpectedly. Nothing was changed that this page can tell; "
    "check the log, then try again."
)
WORKING_WORDS = {
    "save": "Saving the webhook…",
    "remove": "Removing the webhook…",
    "test": "Sending a test message to Discord…",
    "mode": "Saving the bot's alert setting…",
    "bots": "Reading the bots…",
}

#: `BOT-191` — what each `BotAlertMode` is called on the page, and what it means.
BOT_MODE_LABELS = EnumLabels(
    BotAlertMode,
    {
        BotAlertMode.ON: "All messages",
        BotAlertMode.CRITICAL_ONLY: "Critical only",
        BotAlertMode.OFF: "None",
    },
)
BOTS_INTRO = (
    "Choose what each bot may tell you. Critical only silences its fill and cycle "
    "messages and still tells you when it halts, errors or hits a stop loss; None "
    "silences it entirely. A choice is kept for the next start."
)
NO_BOTS = "No bots yet. Create one in the Bots tab, then set what it may tell you here."
BOTS_UNREADABLE = "The bots could not be listed, so none can be set here. Try again."
MODE_SAVED = EnumLabels(
    BotAlertMode,
    {
        BotAlertMode.ON: "Saved: this bot tells you everything.",
        BotAlertMode.CRITICAL_ONLY: (
            "Saved: this bot sends only critical messages, such as a halt or a stop loss."
        ),
        BotAlertMode.OFF: "Saved: this bot sends no messages. A halt will not reach you.",
    },
)
READ_ONLY_NOTE = (
    "This copy of the app is read-only, so it cannot keep these choices. Set them in the "
    "copy that is running."
)


def channel_line(state: DiscordChannelState) -> str:
    """Whether the Discord channel is on, and when a saved webhook starts to matter.

    The lane starts at boot (`ThreadedDeliveryHost`), so a first save or a removal is
    a restart away; a replaced webhook is read at the next send."""
    if state.running and state.usable:
        return "On: alerts go to the saved Discord webhook."
    if state.running and state.stored:
        return (
            "The stored value is not a Discord webhook URL, so Discord alerts are "
            "refused. Save a webhook."
        )
    if state.running:
        return (
            "Removed, but this run still has the Discord channel: its alerts are "
            "refused until you restart the app."
        )
    if state.usable:
        return "Saved, not sending yet: restart the app to start sending."
    if state.stored:
        return "Off: the stored value is not a Discord webhook URL. Save a webhook."
    return "Off: no Discord webhook is saved."


def saved_line(state: DiscordChannelState) -> str:
    if state.usable:
        return f"Saved webhook ending …{state.hint}"
    if state.stored:
        return "A value is stored, but it is not a Discord webhook URL."
    return "No webhook saved."


def send_test_words(outcomes: tuple[ChannelTestOutcome, ...]) -> tuple[str, bool]:
    """`(sentence, is_error)` for the Send test's outcomes."""
    if not outcomes:
        return NOTHING_TO_TEST, True
    failed = [outcome for outcome in outcomes if not outcome.result.ok]
    if not failed:
        return TEST_SENT, False
    lines = []
    for outcome in failed:
        advice = (
            f" Copy the webhook again and save it. {WHERE_TO_COPY_IT}"
            if outcome.result.permanent
            else " Try again in a moment."
        )
        lines.append(f"Test message not sent: {outcome.result.reason}.{advice}")
    return " ".join(lines), True
