"""What the Quiet hours group says (`EPIC-036D6`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.application.quiet_hours_setup import (
    QuietHoursSave,
    QuietHoursState,
)

TITLE = "Quiet hours"
INTRO = (
    "During quiet hours the app holds Warning and Info alerts and sends one summary when they "
    "end. Critical alerts are never held. Save and Turn off act at once: OK and Apply have "
    "nothing to save here."
)
ENABLE = "Hold Warning and Info alerts during these hours"
FROM = "From:"
TO = "To:"
SAVE = "Save quiet hours"
READ_ONLY_NOTE = (
    "This copy of the app is read-only, so quiet hours cannot be changed here. "
    "Use the copy that is running the bots."
)
WORKING = "Saving the quiet hours…"
DOING = "saving the quiet hours"

SAVE_WORDS: dict[QuietHoursSave, tuple[str, bool]] = {
    QuietHoursSave.SAVED: ("Quiet hours saved.", False),
    QuietHoursSave.TURNED_OFF: ("Quiet hours are off.", False),
    QuietHoursSave.NO_PERIOD: (
        (
            "Start and end are the same time, which is no quiet period. Pick two different "
            "times, or turn quiet hours off."
        ),
        True,
    ),
    QuietHoursSave.READ_ONLY: (
        "This copy of the app is read-only: nothing was changed.",
        True,
    ),
    QuietHoursSave.NOT_KEPT: (
        (
            "The quiet hours could not be saved, so they are as they were. Check that the "
            "data folder can be written to, then try again."
        ),
        True,
    ),
}


def zone_line(state: QuietHoursState) -> str:
    if state.enabled:
        start = state.start.isoformat(timespec="minutes")
        end = state.end.isoformat(timespec="minutes")
        return f"Held from {start} to {end} ({state.zone_key})."
    return f"Off. Times are read in your display time zone ({state.zone_key})."
