"""N5 — what one bot may say."""

from __future__ import annotations

from enum import Enum


class BotAlertMode(Enum):
    ON = "on"
    CRITICAL_ONLY = "critical_only"
    OFF = "off"
