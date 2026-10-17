"""`EPIC-042C` — whether the cause of a transient halt has cleared (ADR 042 §2.2).

The recovery policy (`domain/halt_recovery_policy.py`) says *which* reasons may recover and how
long they must stay clear; each kind says *how to see* that one has cleared. This is that
question. The recovery run samples it on the price watch's beat and counts a dwell only while it
answers yes, so a feed that flaps resets the dwell.

@par Extension cases
  · a new common reason - one more branch in each kind's probe, and a test that the probe knows
    every code the effective policy holds (`test_every_recoverable_reason_has_a_probe`);
  · a reason only one kind has - that kind's probe alone.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    HaltCode,
)


class IHaltConditionProbe(ABC):
    """Reads whether a halt's cause is clear now."""

    @abstractmethod
    def knows(self, code: HaltCode) -> bool:
        """Whether this probe can see `code` clear. A code it does not know never clears."""

    @abstractmethod
    def is_clear(self, code: HaltCode, waiting_since: float) -> bool:
        """Whether `code`'s cause is clear now, judged only on what happened since
        `waiting_since` (a reading of the bot's monotonic clock, in seconds): a quiet feed that has
        said nothing since the halt is not clear, however fresh an older reading looks."""
