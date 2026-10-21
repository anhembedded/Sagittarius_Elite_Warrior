"""`EPIC-044B` — what a Grid waiting for its range asks before it lays its ladder (ADR 044 D5).

The Bots screen and the Start use case judge a bot's readiness once, before it starts, from the
world as it is then (the balance, the plan's verdicts, the caps). A bot that waited for days must
ask again at the moment the price enters its range, in the same words: this port is that question.
The answer is a refusal of the plan (the bot halts, `entry_refused`) or a cause that will pass (the
venue could not be read; the bot keeps waiting), never an order.

Extension cases: a venue-specific entry check is one more clause of the readiness assessment, not a
change here; a second kind that waits for its own condition implements this port for itself.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot


@dataclass(frozen=True, slots=True)
class EntryReadiness:
    """Whether the plan may be laid now, and if not, why and whether that will pass."""

    #: The words of what is left, as the Bots screen says them; `""` when the plan may be laid.
    refusal: str = ""
    #: The refusal is a state of the world that passes by itself (the venue could not be read),
    #: not a fault of the plan.
    transient: bool = False

    @property
    def ready(self) -> bool:
        return not self.refusal


class IEntryReadiness(ABC):
    @abstractmethod
    def judge(self, bot: Bot) -> EntryReadiness:
        """The readiness of `bot` to lay its ladder at the price now."""


class NoEntryReadiness(IEntryReadiness):
    """Judges nothing: every plan is ready. The default of a build that wires no judge."""

    def judge(self, bot: Bot) -> EntryReadiness:
        return EntryReadiness()
