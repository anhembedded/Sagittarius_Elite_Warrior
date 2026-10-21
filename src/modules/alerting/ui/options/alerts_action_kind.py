"""The things the Alerts page runs off the UI thread (`EPIC-036D8`).

`ActionOwnershipTracker`'s `TKind`: the value is the key of `alerts_words.WORKING_WORDS` and
`alerts_words.DOING_WORDS`. Split from the presenter, which is at the file-size ceiling.
"""

from __future__ import annotations

from enum import Enum


class AlertsActionKind(str, Enum):
    SAVE = "save"
    REMOVE = "remove"
    TEST = "test"
    MODE = "mode"
    BOTS = "bots"
    TELEGRAM_SAVE = "telegram_save"
    TELEGRAM_REMOVE = "telegram_remove"
    QUIET = "quiet"
    ROUTE = "route"
    CHANNEL = "channel"
    HEARTBEAT = "heartbeat"
