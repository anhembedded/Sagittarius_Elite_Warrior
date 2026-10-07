"""`EPIC-034H` — "what is left before this bot can start"."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetBotReadinessQuery:
    """The bot, and the parameters to judge when they are not yet saved.

    `config` is what **Save and Start** would run: the edits on screen. `None`
    judges the saved parameters, which is what a plain Start runs.
    """

    bot_id: str
    config: Mapping[str, str] | None = None
