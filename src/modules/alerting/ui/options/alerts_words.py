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
from Sagittarius_Elite_Warrior.src.modules.alerting.application.telegram_credentials_setup import (
    TelegramChannelState,
    TelegramRemoval,
    TelegramSave,
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
    "No alert channel is saved, so there is nothing to test. Save a Discord webhook or a "
    "Telegram bot first."
)
UNEXPECTED_HEADLINE = (
    "{doing} failed unexpectedly. Nothing was changed that this page can tell; "
    "check the log, then try again."
)
#: What failed, for the unexpected-failure headline (`UNEXPECTED_HEADLINE`), by action kind.
DOING_WORDS = {
    "save": "Saving the webhook",
    "remove": "Removing the webhook",
    "test": "Sending the test message",
    "mode": "Saving the bot's alert setting",
    "bots": "Reading the bots",
    "telegram_save": "Saving the Telegram bot",
    "telegram_remove": "Removing the Telegram bot",
}
WORKING_WORDS = {
    "save": "Saving the webhook…",
    "remove": "Removing the webhook…",
    "test": "Sending a test message…",
    "mode": "Saving the bot's alert setting…",
    "bots": "Reading the bots…",
    "telegram_save": "Saving the Telegram bot…",
    "telegram_remove": "Removing the Telegram bot…",
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


WHERE_TO_GET_TELEGRAM = (
    "In Telegram: create a bot with @BotFather and copy its token; then send the bot a "
    "message and read your chat id (for example from @userinfobot)."
)

TELEGRAM_SAVE_WORDS: dict[TelegramSave, tuple[str, bool]] = {
    TelegramSave.SAVED: ("Telegram bot saved.", False),
    TelegramSave.EMPTY_TOKEN: ("Paste the bot token first.", True),
    TelegramSave.EMPTY_CHAT: ("Enter the chat id first.", True),
    TelegramSave.NOT_A_BOT_TOKEN: (
        (
            "That is not a Telegram bot token, so nothing was saved. A token looks like "
            f"123456789:AA… {WHERE_TO_GET_TELEGRAM}"
        ),
        True,
    ),
    TelegramSave.NOT_A_CHAT_ID: (
        (
            "That is not a chat id, so nothing was saved. A chat id is a number (a group's "
            f"starts with a minus) or a public channel's @name. {WHERE_TO_GET_TELEGRAM}"
        ),
        True,
    ),
    TelegramSave.STORE_UNAVAILABLE: (
        (
            "The operating system's keyring cannot store a secret here, so nothing was "
            "saved. Unlock or enable the keyring, then save again."
        ),
        True,
    ),
    TelegramSave.OVERRIDDEN: (
        (
            "Saved to the keyring, but this machine reads the Telegram credentials from a "
            "systemd credential or secret file first, so the saved ones are not used. "
            "Change them where that is provisioned."
        ),
        True,
    ),
}

TELEGRAM_REMOVAL_WORDS: dict[TelegramRemoval, tuple[str, bool]] = {
    TelegramRemoval.REMOVED: ("Telegram bot removed.", False),
    TelegramRemoval.NOTHING_STORED: ("No Telegram bot was saved.", False),
    TelegramRemoval.STORE_UNAVAILABLE: (
        (
            "The operating system's keyring cannot remove a secret here, so the bot is "
            "still saved. Unlock or enable the keyring, then remove it again."
        ),
        True,
    ),
    TelegramRemoval.STILL_SET_ELSEWHERE: (
        (
            "The keyring entry is removed, but the Telegram credentials are still set by a "
            "systemd credential or secret file, so the channel stays configured. Remove "
            "them where that is provisioned."
        ),
        True,
    ),
}


def telegram_channel_line(state: TelegramChannelState) -> str:
    """Whether the Telegram channel is on, and when saved credentials start to matter: the
    lane starts at boot, a replaced pair is read at the next send."""
    if state.running and state.usable:
        return "On: alerts go to the saved Telegram bot."
    if state.running and state.stored:
        return (
            "The stored Telegram values are incomplete or not of the shape Telegram "
            "issues, so Telegram alerts are refused. Save the bot token and chat id."
        )
    if state.running:
        return (
            "Removed, but this run still has the Telegram channel: its alerts are refused "
            "until you restart the app."
        )
    if state.usable:
        return "Saved, not sending yet: restart the app to start sending."
    if state.stored:
        return (
            "Off: the stored Telegram values are incomplete or not of the shape Telegram "
            "issues. Save the bot token and chat id."
        )
    return "Off: no Telegram bot is saved."


def telegram_saved_line(state: TelegramChannelState) -> str:
    if state.usable:
        return f"Saved bot token ending …{state.hint}, chat {state.chat}"
    if state.stored:
        return "Values are stored, but they are not a complete Telegram bot."
    return "No bot saved."


def _channel_name(channel_id: str) -> str:
    return channel_id.capitalize()


def _failure_advice(outcome: ChannelTestOutcome) -> str:
    if not outcome.result.permanent:
        return " Try again in a moment."
    if outcome.channel_id == "telegram":
        return f" Check the bot token and chat id, then save them again. {WHERE_TO_GET_TELEGRAM}"
    return f" Copy the webhook again and save it. {WHERE_TO_COPY_IT}"


def send_test_words(outcomes: tuple[ChannelTestOutcome, ...]) -> tuple[str, bool]:
    """`(sentence, is_error)` for the Send test's outcomes."""
    if not outcomes:
        return NOTHING_TO_TEST, True
    failed = [outcome for outcome in outcomes if not outcome.result.ok]
    if not failed:
        names = " and ".join(_channel_name(o.channel_id) for o in outcomes)
        where = "channel" if len(outcomes) == 1 else "channels"
        return f"Test message sent to {names}. Check the {where}.", False
    reached = [o for o in outcomes if o.result.ok]
    lines = [f"Sent to {_channel_name(o.channel_id)}." for o in reached]
    lines += [
        f"Test message not sent: {outcome.result.reason}.{_failure_advice(outcome)}"
        for outcome in failed
    ]
    return " ".join(lines), True
