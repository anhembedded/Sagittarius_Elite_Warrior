"""`EPIC-029B` — "every bot, for the list"."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ListBotsQuery:
    """No parameters: the list shows every bot."""
