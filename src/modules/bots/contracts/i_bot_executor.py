"""`EPIC-029B` — the seam a kind's executor sits behind (ADR D2, D9).

The executor is the actor that runs one bot (`EPIC-029E`): it places and
cancels the bot's orders through trading and reports lifecycle events back.
Each method is a command: it asks the actor to begin, and the actor reports the
outcome as a lifecycle event (`ladder_ready`, `start_refused`,
`stop_confirmed`, `fault`), never as a return value, because every one of these
takes exchange round trips the caller must not wait on.

Only the seam is here. No executor exists before `EPIC-029E`, so nothing in
this module binds one yet.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot


class BaseHandling(str, Enum):
    """What Stop does with the base asset the bot bought (ADR O3)."""

    KEEP = "KEEP"
    SELL_AT_MARKET = "SELL_AT_MARKET"


class IBotExecutor(ABC):
    """Runs one bot. Every method asks; the outcome arrives as a lifecycle event."""

    @abstractmethod
    def start(self) -> None:
        """Place the opening buy and the ladder (ADR §3.4, D21)."""

    @abstractmethod
    def pause(self) -> None:
        """Stop placing; keep recording fills."""

    @abstractmethod
    def resume(self) -> None:
        """Place what the pause held back, or re-plan from HALTED (ADR D13)."""

    @abstractmethod
    def stop(self, base: BaseHandling) -> None:
        """Cancel every tagged order, then keep or sell the base (ADR O3)."""


class IBotExecutorFactory(ABC):
    """Builds the executor for one bot of one kind."""

    @abstractmethod
    def create(self, bot: Bot) -> IBotExecutor:
        """A new executor for `bot`."""
