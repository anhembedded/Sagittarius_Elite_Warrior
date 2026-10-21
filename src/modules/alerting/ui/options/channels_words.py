"""What the channels group says (`EPIC-036D8`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.application.channels_setup import (
    ChannelSwitch,
)

TITLE = "Channels"
INTRO = (
    "Each channel that is running can be switched off without removing its webhook or bot: "
    "nothing is sent there until it is switched on again. A switch acts at once: OK and Apply "
    "have nothing to save here."
)
NO_CHANNELS = (
    "No alert channel is running. Set one up above; a channel added now appears here after "
    "the app restarts."
)
ALL_OFF = "Every channel is switched off, so no alert is sent anywhere, a Critical one included."
READ_ONLY_NOTE = (
    "This copy of the app is read-only, so the channels cannot be switched here. "
    "Use the copy that is running the bots."
)
WORKING = "Saving the channel switch…"
DOING = "saving the channel switch"

SAVE_WORDS: dict[ChannelSwitch, tuple[str, bool]] = {
    ChannelSwitch.TURNED_ON: ("Channel switched on.", False),
    ChannelSwitch.TURNED_OFF: (
        "Channel switched off. Nothing is sent there now.",
        False,
    ),
    ChannelSwitch.READ_ONLY: (
        "This copy of the app is read-only: nothing was changed.",
        True,
    ),
    ChannelSwitch.UNKNOWN_CHANNEL: (
        (
            "That channel is not running in this session, so the switch would reach nothing. "
            "Restart the app after setting a channel up."
        ),
        True,
    ),
    ChannelSwitch.NOT_KEPT: (
        (
            "The switch could not be saved, so it is as it was. Check that the data folder "
            "can be written to, then try again."
        ),
        True,
    ),
}
