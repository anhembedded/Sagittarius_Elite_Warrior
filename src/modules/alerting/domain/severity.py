"""How urgent an alert is (`EPIC-036A`)."""

from __future__ import annotations

from enum import IntEnum


class Severity(IntEnum):
    """Ordered, so `CRITICAL > WARNING > INFO` is the priority the worker sorts by.

    - `CRITICAL` — money is at risk, act now;
    - `WARNING` — the bot handled it, the owner should know;
    - `INFO` — a summary or a heartbeat.
    """

    INFO = 1
    WARNING = 2
    CRITICAL = 3
