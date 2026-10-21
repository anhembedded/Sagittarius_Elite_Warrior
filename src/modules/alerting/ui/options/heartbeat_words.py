"""What the heartbeat group says (`EPIC-036D9`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.application.heartbeat_setup import (
    DEFAULT_HOURS,
    HeartbeatSave,
)

TITLE = "Heartbeat"
INTRO = (
    "While nothing is wrong the app still sends a short message saying the bots are running, so "
    "silence means something. Choose how often. The default is every {default}. A change acts at "
    "once: OK and Apply have nothing to save here."
)
FIELD = "Send a heartbeat every:"
READ_ONLY_NOTE = (
    "This copy of the app is read-only, so the heartbeat cannot be changed here. "
    "Use the copy that is running the bots."
)
WORKING = "Saving the heartbeat interval…"
DOING = "saving the heartbeat interval"


def hours_text(hours: int) -> str:
    return f"{hours} hour" if hours == 1 else f"{hours} hours"


def intro() -> str:
    return INTRO.format(default=hours_text(DEFAULT_HOURS))


def choice_text(hours: int) -> str:
    """`6 hours (default)` for the default, `1 hour` and the like for the rest."""
    text = hours_text(hours)
    return f"{text} (default)" if hours == DEFAULT_HOURS else text


SAVE_WORDS: dict[HeartbeatSave, tuple[str, bool]] = {
    HeartbeatSave.SAVED: ("Heartbeat interval saved.", False),
    HeartbeatSave.BACK_TO_DEFAULT: (
        "The heartbeat is back to its default interval.",
        False,
    ),
    HeartbeatSave.NOT_A_CHOICE: (
        "That interval is not one of the choices: nothing was changed.",
        True,
    ),
    HeartbeatSave.READ_ONLY: (
        "This copy of the app is read-only: nothing was changed.",
        True,
    ),
    HeartbeatSave.NOT_KEPT: (
        (
            "The heartbeat interval could not be saved, so it is as it was. Check that the data "
            "folder can be written to, then try again."
        ),
        True,
    ),
}
