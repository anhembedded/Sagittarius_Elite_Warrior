"""How a route cell sounds on the owner's phone."""

from __future__ import annotations

from enum import Enum


class Loudness(Enum):
    """`SILENT` is sent without a sound (Discord `@silent`, Telegram
    `disable_notification`); `OFF` is not sent."""

    LOUD = "loud"
    SILENT = "silent"
    OFF = "off"
