"""What the routing matrix says (`EPIC-036D7`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.application.routing_setup import (
    RouteSave,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness

TITLE = "Who hears what"
INTRO = (
    "Each row is a kind of alert and each column a channel that is running. Loud makes the "
    "phone ring, Silent sends the message without a sound, Off does not send it there. "
    "Default is Loud for a Critical alert and Silent for the rest. A choice acts at once: OK "
    "and Apply have nothing to save here."
)
COVER_NOTE = (
    "A Critical alert always reaches two channels when two are set up, and at least one of them "
    "rings, whatever is chosen here, because a push that never arrives or arrives without a "
    "sound is a known failure."
)
NO_CHANNELS = (
    "No alert channel is running, so there is nothing to route. Set one up above; a channel "
    "added now appears here after the app restarts."
)
READ_ONLY_NOTE = (
    "This copy of the app is read-only, so the routing cannot be changed here. "
    "Use the copy that is running the bots."
)
WORKING = "Saving the routing…"
DOING = "saving the routing"

#: The rows, in the order shown: a name, and what falls in it.
GROUP_ROWS: tuple[tuple[AlertGroup, str, str], ...] = (
    (
        AlertGroup.BOT_EVENTS,
        "Bot events",
        (
            "a bot halted or failed, a stop loss or take profit, a stop that failed, a loss "
            "cap, liquidation risk, a recovery"
        ),
    ),
    (
        AlertGroup.INFRASTRUCTURE,
        "App and exchange problems",
        (
            "the price feed stale, the account stream down, the API key rejected, storage or "
            "application failure"
        ),
    ),
    (
        AlertGroup.NOTICES,
        "Notices",
        "rate limited, the price left the range, an alert channel failing",
    ),
    (
        AlertGroup.ROUTINE,
        "Routine messages",
        ("filled orders, closed positions, the heartbeat, the daily summary, tests"),
    ),
)

#: The choices of a cell; the empty value is the default (no route).
DEFAULT_VALUE = ""
CHOICES: tuple[tuple[str, str], ...] = (
    (DEFAULT_VALUE, "Default"),
    (Loudness.LOUD.value, "Loud"),
    (Loudness.SILENT.value, "Silent"),
    (Loudness.OFF.value, "Off"),
)

SAVE_WORDS: dict[RouteSave, tuple[str, bool]] = {
    RouteSave.SAVED: ("Routing saved.", False),
    RouteSave.BACK_TO_DEFAULT: ("That cell is back to its default.", False),
    RouteSave.READ_ONLY: (
        "This copy of the app is read-only: nothing was changed.",
        True,
    ),
    RouteSave.UNKNOWN_CHANNEL: (
        (
            "That channel is not running in this session, so the choice would reach nothing. "
            "Restart the app after setting a channel up."
        ),
        True,
    ),
    RouteSave.NOT_KEPT: (
        (
            "The routing could not be saved, so it is as it was. Check that the data folder "
            "can be written to, then try again."
        ),
        True,
    ),
}


def channel_title(channel_id: str) -> str:
    return channel_id.capitalize()
