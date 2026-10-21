"""What the Alerts screen says (`EPIC-036D2`): every sentence and word in one file.

Severity and delivery state are told in words, never by colour alone. A text drawn from
outside (an exception) is its type name only, as on the Options page.
"""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.alert_history_report import (
    ChannelHealth,
    ChannelOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity

SEVERITY_WORDS = {
    Severity.INFO: "Info",
    Severity.WARNING: "Warning",
    Severity.CRITICAL: "Critical",
}

STATE_WORDS = {
    DeliveryState.PENDING: "waiting",
    DeliveryState.RETRYING: "retrying",
    DeliveryState.SENT: "delivered",
    DeliveryState.FAILED: "failed",
    DeliveryState.EXPIRED: "expired",
    DeliveryState.DROPPED: "dropped",
}

#: A try count is worth telling only for a delivery that has not simply gone through.
_SHOWS_ATTEMPTS = frozenset(
    {DeliveryState.RETRYING, DeliveryState.FAILED, DeliveryState.EXPIRED}
)

NOT_SENT = "not sent (muted, or no channel for it)"
EMPTY_TEXT = (
    "No alerts to show. An alert appears here when the app raises one and the filter "
    "allows its severity."
)
NO_CHANNELS = (
    "No alert channel is configured, so nothing leaves this app. Add a Discord webhook in "
    "Tools → Options → Alerts."
)
READING = "Reading the alert history…"
READ_FAILED = (
    "Reading the alert history failed ({error_type}). The list below is the last one read; "
    "check the log, then press Refresh."
)

#: The filter's choices, in the order the combo lists them.
FILTER_ALL = "All alerts"
FILTER_WARNING = "Warning and above"
FILTER_CRITICAL = "Critical only"
FILTER_CHOICES: tuple[tuple[str, Severity | None], ...] = (
    (FILTER_ALL, None),
    (FILTER_WARNING, Severity.WARNING),
    (FILTER_CRITICAL, Severity.CRITICAL),
)


#: The status-bar indicator (`EPIC-036D3`): the state in words, a failing channel also by icon.
INDICATOR_OK = "Alerts: ok"
INDICATOR_OFF = "Alerts: no channel"
INDICATOR_UNKNOWN = "Alerts: unknown"
INDICATOR_UNKNOWN_TIP = (
    "The alert history could not be read ({error_type}), so the channels' state is not known. "
    "Open the Alerts mode, check the log, then press Refresh."
)
INDICATOR_TIP = "Open the Alerts mode to see what was sent and where it stands."


def indicator_text(channels: Sequence[ChannelHealth]) -> str:
    """`Alerts: ok`, `Alerts: no channel`, or `Alerts: Discord failing`."""
    if not channels:
        return INDICATOR_OFF
    failing = [channel_name(c.channel_id) for c in channels if c.failing]
    if not failing:
        return INDICATOR_OK
    return f"Alerts: {' and '.join(failing)} failing"


def channel_name(channel_id: str) -> str:
    return channel_id.capitalize()


def delivery_text(outcomes: Sequence[ChannelOutcome]) -> str:
    """`Discord: delivered; Telegram: retrying ×2`."""
    if not outcomes:
        return NOT_SENT
    return "; ".join(_outcome_text(outcome) for outcome in outcomes)


def _outcome_text(outcome: ChannelOutcome) -> str:
    text = f"{channel_name(outcome.channel_id)}: {STATE_WORDS[outcome.state]}"
    if outcome.state in _SHOWS_ATTEMPTS and outcome.attempts > 0:
        return f"{text} ×{outcome.attempts}"
    return text


def alert_text(title: str, count: int) -> str:
    return f"{title} (×{count})" if count > 1 else title


def channels_line(channels: Sequence[ChannelHealth]) -> str:
    """`Discord: working · Telegram: failing (2 waiting)`."""
    if not channels:
        return NO_CHANNELS
    return " · ".join(_channel_text(channel) for channel in channels)


def _channel_text(channel: ChannelHealth) -> str:
    text = f"{channel_name(channel.channel_id)}: {'failing' if channel.failing else 'working'}"
    return f"{text} ({channel.waiting} waiting)" if channel.waiting else text


def failing_notice(channels: Sequence[ChannelHealth]) -> str:
    """The sentence for a notice bar, or `""` when every channel is getting its alerts."""
    failing = [channel_name(c.channel_id) for c in channels if c.failing]
    if not failing:
        return ""
    names = " and ".join(failing)
    return (
        f"{names} is not getting your alerts: its latest delivery did not go through. "
        "Check the channel's setup in Tools → Options → Alerts."
        if len(failing) == 1
        else f"{names} are not getting your alerts: their latest deliveries did not go "
        "through. Check the channels' setup in Tools → Options → Alerts."
    )
