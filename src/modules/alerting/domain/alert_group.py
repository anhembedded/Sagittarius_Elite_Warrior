"""The rows of the Options matrix: what an owner routes, not what code raises."""

from __future__ import annotations

from enum import Enum


class AlertGroup(Enum):
    """A fixed set in code; a new `AlertKind` joins one of these.

    The Options page (`EPIC-036D`) shows one row per group and one column per
    channel; each cell is a `Loudness`.
    """

    BOT_EVENTS = "bot_events"
    INFRASTRUCTURE = "infrastructure"
    NOTICES = "notices"
    ROUTINE = "routine"
